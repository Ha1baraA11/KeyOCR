"""测试 OCR 区域自动检测"""
import cv2
import numpy as np
import sys

def detect_text_region(frame):
    """检测文字密集区域，返回 (x, y, w, h) 相对比例"""
    h_img, w_img = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 自适应二值化
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 5
    )

    # 水平形态学闭操作，连接同一行的文字
    kernel_h = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel_h)

    # 垂直形态学闭操作，连接相邻行
    kernel_v = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 10))
    closed = cv2.morphologyEx(closed, cv2.MORPH_CLOSE, kernel_v)

    # 查找轮廓
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h_img * w_img * 0.003  # 0.3% of image
    valid_boxes = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        area = w * h
        rel_h = h / h_img
        rel_w = w / w_img
        # 过滤：面积够大，高度合理，宽度不能太窄
        if area > min_area and 0.01 < rel_h < 0.40 and rel_w > 0.02:
            valid_boxes.append((x, y, w, h))

    if not valid_boxes:
        return None

    # 合并所有文字框
    x1 = min(b[0] for b in valid_boxes)
    y1 = min(b[1] for b in valid_boxes)
    x2 = max(b[0] + b[2] for b in valid_boxes)
    y2 = max(b[1] + b[3] for b in valid_boxes)

    # 扩展 5% margin
    margin_x = int((x2 - x1) * 0.05)
    margin_y = int((y2 - y1) * 0.05)
    x1 = max(0, x1 - margin_x)
    y1 = max(0, y1 - margin_y)
    x2 = min(w_img, x2 + margin_x)
    y2 = min(h_img, y2 + margin_y)

    return (x1 / w_img, y1 / h_img, (x2 - x1) / w_img, (y2 - y1) / h_img)


def draw_detection(frame, region):
    """在帧上绘制检测框"""
    h, w = frame.shape[:2]
    result = frame.copy()

    if region is None:
        cv2.putText(result, "No text detected", (50, 50),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        return result

    rx, ry, rw, rh = region
    x1, y1 = int(rx * w), int(ry * h)
    x2, y2 = int((rx + rw) * w), int((ry + rh) * h)

    # 半透明填充
    overlay = result.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), (0, 0, 255), -1)
    cv2.addWeighted(overlay, 0.3, result, 0.7, 0, result)

    # 边框
    cv2.rectangle(result, (x1, y1), (x2, y2), (0, 0, 255), 3)

    # 标注信息
    info = f"x={rx:.2f} y={ry:.2f} w={rw:.2f} h={rh:.2f}"
    cv2.putText(result, info, (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

    return result


def main():
    video_path = "/Users/zetazero/Downloads/测试.mp4"
    if len(sys.argv) > 1:
        video_path = sys.argv[1]

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"无法打开视频: {video_path}")
        return

    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("无法读取第一帧")
        return

    h, w = frame.shape[:2]
    print(f"视频分辨率: {w}x{h}")

    # 检测文字区域
    region = detect_text_region(frame)
    if region:
        rx, ry, rw, rh = region
        print(f"检测到文字区域: x={rx:.3f} y={ry:.3f} w={rw:.3f} h={rh:.3f}")
        print(f"像素坐标: ({int(rx*w)}, {int(ry*h)}) -> ({int((rx+rw)*w)}, {int((ry+rh)*h)})")
    else:
        print("未检测到文字区域")

    # 绘制结果并保存
    result = draw_detection(frame, region)
    output_path = "/Users/zetazero/Downloads/region_detect_result.jpg"
    cv2.imwrite(output_path, result)
    print(f"结果已保存: {output_path}")

    # 也保存中间处理步骤的可视化
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, 21, 5
    )
    cv2.imwrite("/Users/zetazero/Downloads/region_detect_binary.jpg", binary)
    print("二值化结果: /Users/zetazero/Downloads/region_detect_binary.jpg")


if __name__ == "__main__":
    main()
