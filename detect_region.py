"""视频中间区域自动检测脚本。
多帧采样检测，通过边缘检测自动识别中间区域的合适框选范围。
"""

import cv2
import numpy as np
import os
import sys


def detect_center_region(frame):
    """检测帧中字幕卡片区域。

    策略：用 Sobel 水平边缘找到字幕卡片的上下边界。
    字幕卡片是纯色块，和复杂背景之间有极强的水平边缘。
    只看横跨画面宽度 ≥50% 的边缘行（排除局部噪点）。

    Returns:
        (x, y, w, h) 框选区域（像素坐标）
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Sobel 水平边缘
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobel = np.abs(sobel_y)

    # 只看中间 20%-80%
    search_top = int(h * 0.20)
    search_bottom = int(h * 0.80)

    # 每行：统计边缘强度超过阈值的列数占比（横跨宽度）
    row_threshold = np.percentile(abs_sobel, 80)
    edge_width_ratio = np.mean(abs_sobel > row_threshold, axis=1)

    # 只保留横跨 ≥50% 宽度的行
    wide_mask = edge_width_ratio >= 0.50
    mid_mask = wide_mask[search_top:search_bottom]

    # 聚类通过的行（间距 < 10px 的算一组）
    passed_rows = np.where(mid_mask)[0] + search_top
    if len(passed_rows) < 2:
        return (0, int(h * 0.25), w, int(h * 0.5))

    clusters = []
    start = passed_rows[0]
    for i in range(1, len(passed_rows)):
        if passed_rows[i] - passed_rows[i-1] > 10:
            clusters.append((start, passed_rows[i-1]))
            start = passed_rows[i]
    clusters.append((start, passed_rows[-1]))

    # 取每个聚类的中心线和综合得分（宽度比 × 边缘强度）
    cluster_info = []
    for c_start, c_end in clusters:
        center = (c_start + c_end) // 2
        max_ratio = np.max(edge_width_ratio[c_start:c_end+1])
        mean_strength = np.mean(abs_sobel[c_start:c_end+1, :])
        score = max_ratio * mean_strength
        cluster_info.append((center, score))

    if len(cluster_info) < 2:
        return (0, int(h * 0.25), w, int(h * 0.5))

    # 按综合得分排序，选最强的两个
    cluster_info.sort(key=lambda x: x[1], reverse=True)
    top_edge = min(cluster_info[0][0], cluster_info[1][0])
    bottom_edge = max(cluster_info[0][0], cluster_info[1][0])

    if bottom_edge - top_edge < 10:
        return (0, int(h * 0.25), w, int(h * 0.5))

    return (0, top_edge, w, bottom_edge - top_edge)


def detect_stable_region(video_path, coarse_fps=9, sample_count=16):
    """从视频多帧采样，投票取最稳定区域。

    多数帧会给出正确结果，少数帧误检。用聚类投票选出正确结果。

    Returns:
        (x, y, w, h) 框选区域（像素坐标）
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None

    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    interval = max(1, int(fps / coarse_fps))
    coarse_total = total // interval

    step = max(1, coarse_total // sample_count)
    indices = [i * interval for i in range(0, coarse_total, step)][:sample_count]

    regions = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        r = detect_center_region(frame)
        if 0.05 <= r[3] / frame_h <= 0.50:
            regions.append(r)
    cap.release()

    if len(regions) < 2:
        return (0, int(frame_h * 0.25), frame_w, int(frame_h * 0.5))

    # 按 y 值聚类（间距 < 10% 帧高度算一组）
    regions.sort(key=lambda r: r[1])
    threshold = frame_h * 0.10
    groups = [[regions[0]]]
    for r in regions[1:]:
        if r[1] - groups[-1][-1][1] < threshold:
            groups[-1].append(r)
        else:
            groups.append([r])

    largest = max(groups, key=len)
    ys = sorted([r[1] for r in largest])
    bhs = sorted([r[3] for r in largest])
    return (0, ys[len(ys) // 2], frame_w, bhs[len(bhs) // 2])


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
