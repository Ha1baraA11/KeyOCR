"""视频中间区域自动检测脚本。
多帧采样检测，通过边缘检测自动识别中间区域的合适框选范围。
"""

import cv2
import numpy as np
import os
import sys


def detect_center_region(frame):
    """检测帧中最大的纯色区域。

    策略：背景杂乱但中间有纯色块（纸张/屏幕），
    通过局部方差检测低方差区域，找到最大的纯色块。

    Returns:
        (x, y, w, h) 框选区域（像素坐标）
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 计算局部标准差（纯色区域标准差低）
    ksize = max(15, min(h, w) // 30)
    if ksize % 2 == 0:
        ksize += 1
    mean = cv2.blur(gray.astype(np.float32), (ksize, ksize))
    sq_mean = cv2.blur((gray.astype(np.float32)) ** 2, (ksize, ksize))
    local_std = np.sqrt(np.maximum(sq_mean - mean ** 2, 0))

    # 用 Otsu 自适应阈值分离纯色和非纯色
    std_u8 = np.clip(local_std / local_std.max() * 255, 0, 255).astype(np.uint8)
    _, mask = cv2.threshold(std_u8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # 形态学清理：用较小的核，避免合并相邻区域
    small_ksize = max(3, ksize // 3)
    if small_ksize % 2 == 0:
        small_ksize += 1
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (small_ksize, small_ksize))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    # 找轮廓，取面积最大的
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return (0, int(h * 0.25), w, int(h * 0.5))

    largest = max(contours, key=cv2.contourArea)
    x, y, bw, bh = cv2.boundingRect(largest)

    # 精确裁剪：逐行检查轮廓内实际方差，只保留真正纯色的行
    contour_mask = np.zeros((h, w), dtype=np.uint8)
    cv2.drawContours(contour_mask, [largest], -1, 255, -1)
    row_mean_std = []
    for row in range(y, y + bh):
        row_pixels = local_std[row, :][contour_mask[row, :] > 0]
        if len(row_pixels) > 0:
            row_mean_std.append(np.mean(row_pixels))
        else:
            row_mean_std.append(float('inf'))

    # 用 Otsu 对行均值方差再做一次分割，只保留纯色行
    if len(row_mean_std) > 1:
        row_arr = np.array(row_mean_std)
        row_u8 = np.clip(row_arr / row_arr.max() * 255, 0, 255).astype(np.uint8)
        _, row_mask = cv2.threshold(row_u8, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        pure_rows = np.where(row_mask > 0)[0]
        if len(pure_rows) > 0:
            y = y + pure_rows[0]
            bh = pure_rows[-1] - pure_rows[0] + 1

    # 宽度取全宽
    return (0, y, w, bh)


def detect_stable_region(video_path, coarse_fps=9, sample_count=8):
    """从视频多帧采样，取中位数区域，避免单帧偏差。

    优先密集采样前段帧（前 25%），若全部异常则回退到全范围采样。

    Returns:
        (x, y, w, h) 框选区域（像素坐标）
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    interval = max(1, int(fps / coarse_fps))
    coarse_total = total // interval

    def _sample(frame_indices):
        regions = []
        for idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ret, frame = cap.read()
            if not ret:
                break
            regions.append(detect_center_region(frame))
        return regions

    # 优先采样前 25% 的粗扫帧
    early_count = max(1, coarse_total // 4)
    step = max(1, early_count // sample_count)
    early_indices = [i * interval for i in range(0, early_count, step)][:sample_count]
    regions = _sample(early_indices)
    good = [r for r in regions if 0.20 <= r[3] / frame_h <= 0.40]

    if len(good) < 2:
        # 前段帧不够，扩大到全范围
        step2 = max(1, coarse_total // sample_count)
        all_indices = [i * interval for i in range(0, coarse_total, step2)][:sample_count]
        regions = _sample(all_indices)
        good = [r for r in regions if 0.20 <= r[3] / frame_h <= 0.40]

    cap.release()

    if not good:
        good = regions
    if not good:
        return (0, int(frame_h * 0.25), int(frame_h * 0.5))

    # 取中位数
    ys = sorted([r[1] for r in good])
    bhs = sorted([r[3] for r in good])
    _, _, w, _ = good[0]
    return (0, ys[len(ys) // 2], w, bhs[len(bhs) // 2])


def main():
    video_path = sys.argv[1] if len(sys.argv) > 1 else "/Users/zetazero/Downloads/测试4.MP4"
    output_path = video_path.rsplit(".", 1)[0] + "_ocr_region.png"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        sys.exit(1)

    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    print(f"视频分辨率: {w}x{h}")

    # 多帧采样检测
    x, y, box_w, box_h = detect_stable_region(video_path)
    print(f"检测到的框选区域: x={x}, y={y}, w={box_w}, h={box_h}")
    print(f"框占帧高度: {box_h/h*100:.1f}%")

    # 读取第一帧绘制框
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if ret:
        result = frame.copy()
        cv2.rectangle(result, (x, y), (x + box_w, y + box_h), (0, 255, 0), 3)
        label = f"Region: y={y}, h={box_h}"
        cv2.putText(result, label, (10, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imwrite(output_path, result)
        print(f"结果已保存: {output_path}")


if __name__ == "__main__":
    main()
