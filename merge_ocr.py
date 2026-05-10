"""OCR 结果本地合并脚本。
把相邻帧中重复的文本合并成完整的句子。
"""

import re
import sys


def parse_ocr_file(filepath):
    """解析 OCR 结果文件，返回 [(frame_name, [lines]), ...]"""
    frames = []
    current_frame = None
    current_lines = []

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            # 匹配帧头
            m = re.match(r'^=== (frame_\d+\.png).* ===$', line)
            if m:
                if current_frame is not None:
                    frames.append((current_frame, current_lines))
                current_frame = m.group(1)
                current_lines = []
            elif line == '(无文字)':
                continue
            elif line.strip() and current_frame is not None:
                current_lines.append(line.strip())

    if current_frame is not None:
        frames.append((current_frame, current_lines))

    return frames


def find_overlap(prev_text, curr_text):
    """找到 prev_text 和 curr_text 的重叠部分。
    返回 curr_text 中新增的部分。

    策略：
    1. 如果 curr_text 是 prev_text 的前缀 → 完全重复，返回空
    2. 如果 prev_text 是 curr_text 的前缀 → curr_text 是扩展，返回新增部分
    3. 从最长重叠开始尝试匹配
    """
    if not prev_text or not curr_text:
        return curr_text

    # curr_text 是 prev_text 的前缀 → 完全重复
    if prev_text.startswith(curr_text):
        return ""

    # prev_text 是 curr_text 的前缀 → 扩展
    if curr_text.startswith(prev_text):
        return curr_text[len(prev_text):]

    # 尝试从最长重叠开始匹配
    max_overlap = min(len(prev_text), len(curr_text))
    for length in range(max_overlap, 0, -1):
        if prev_text[-length:] == curr_text[:length]:
            return curr_text[length:]

    return curr_text


def find_common_prefix_len(s1, s2):
    """找到两个字符串的最长公共前缀长度"""
    i = 0
    while i < min(len(s1), len(s2)) and s1[i] == s2[i]:
        i += 1
    return i


def merge_frames(frames):
    """合并相邻帧的文本。

    策略：
    1. 如果当前帧是前一帧的前缀 → 跳过当前帧（前一帧更完整）
    2. 如果前一帧是当前帧的前缀 → 用当前帧替换前一帧（当前帧更完整）
    3. 如果有重叠（公共前缀够长）→ 保留最长的版本
    4. 否则 → 保留两帧
    """
    if not frames:
        return []

    # 预处理：把每帧的行拼接成字符串
    frame_texts = []
    for frame_name, lines in frames:
        if lines:
            frame_texts.append("".join(lines))

    if not frame_texts:
        return []

    merged = [frame_texts[0]]

    for i in range(1, len(frame_texts)):
        curr_text = frame_texts[i]
        prev_text = merged[-1]

        # 当前帧是前一帧的前缀 → 跳过
        if prev_text.startswith(curr_text):
            continue

        # 前一帧是当前帧的前缀 → 替换
        if curr_text.startswith(prev_text):
            merged[-1] = curr_text
            continue

        # 找公共前缀
        prefix_len = find_common_prefix_len(prev_text, curr_text)

        # 公共前缀足够长（超过较短文本的 50%）→ 认为是同一句话
        min_len = min(len(prev_text), len(curr_text))
        if min_len > 0 and prefix_len / min_len > 0.5:
            # 保留最长的版本
            if len(curr_text) > len(prev_text):
                merged[-1] = curr_text
            continue

        # 尝试找重叠（后缀和前缀匹配）
        max_overlap = min(len(prev_text), len(curr_text))
        found = False
        for length in range(max_overlap, 0, -1):
            if prev_text[-length:] == curr_text[:length]:
                # 合并：前一帧 + 当前帧的新增部分
                merged[-1] = prev_text + curr_text[length:]
                found = True
                break

        if not found:
            # 无重叠，保留为独立句子
            merged.append(curr_text)

    return merged


def main():
    input_path = "/Users/zetazero/Downloads/测试2_frames/ocr_results.txt"
    output_path = "/Users/zetazero/Downloads/测试2_frames/ocr-最终版.txt"

    frames = parse_ocr_file(input_path)
    print(f"解析到 {len(frames)} 帧")

    merged = merge_frames(frames)
    print(f"合并后 {len(merged)} 条")

    # 输出结果
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, text in enumerate(merged, 1):
            f.write(f"{text}\n")

    print(f"已保存到: {output_path}")

    # 打印预览
    print("\n--- 预览前 20 条 ---")
    for i, text in enumerate(merged[:20], 1):
        print(f"{i:3d}. {text}")


if __name__ == "__main__":
    main()
