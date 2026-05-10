"""视频中间区域自动检测脚本。
截取第一帧，通过边缘检测自动识别中间区域的合适框选范围。
"""

import cv2
import numpy as np
import sys


def detect_center_region(frame):
    """检测帧中最大的纯色区域。

    策略：背景杂乱但中间有纯色块（纸张/屏幕），
    通过局部方差检测低方差区域，找到最大的纯色块。

    Returns:
        (x, y, w, h) 框选区域
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


def main():
    video_path = "/Users/zetazero/Downloads/测试3.mp4"
    output_path = "/Users/zetazero/Downloads/first_frame_region3.png"

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        sys.exit(1)

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("无法读取第一帧")
        sys.exit(1)

    h, w = frame.shape[:2]
    print(f"视频分辨率: {w}x{h}")

    # 检测中间区域
    x, y, box_w, box_h = detect_center_region(frame)
    print(f"检测到的框选区域: x={x}, y={y}, w={box_w}, h={box_h}")
    print(f"框占帧高度: {box_h/h*100:.1f}%")

    # 在帧上绘制框
    result = frame.copy()
    cv2.rectangle(result, (x, y), (x + box_w, y + box_h), (0, 255, 0), 3)

    # 添加标签
    label = f"Region: y={y}, h={box_h}"
    cv2.putText(result, label, (10, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

    cv2.imwrite(output_path, result)
    print(f"结果已保存: {output_path}")


if __name__ == "__main__":
    main()
