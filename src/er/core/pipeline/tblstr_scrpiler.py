from dataclasses import dataclass
from pathlib import Path

from er.utils.console import console
from er.utils.binary import BinaryReader, U32, Bytes, String, se, de
from er.utils.fs import PathLike, to_path
from er.utils.misc import read_json, write_json


def invert_bytes(b: bytes) -> bytes:
    """将字节按位取反"""
    return bytes((~byte_value) & 0xFF for byte_value in b)


@dataclass(slots=True)
class ItemBuf:
    """TBLSTR.ARC 中 Item 的缓冲区结构"""

    str: String
    rest_bytes: Bytes


@dataclass(slots=True)
class Item:
    """TBLSTR.ARC 中的单个条目"""

    unknown_arg: U32
    buf_len: U32
    buf: ItemBuf
    start_offset: int  # Item 在 ARC 文件中的起始偏移（用于索引转换）


@dataclass(slots=True)
class TblStrData:
    """TBLSTR 文件的完整数据"""

    file_len: U32
    items: list[Item]


def parse_tblstr_arc(arc_data: bytes) -> TblStrData:
    """
    解析 TBLSTR.ARC 文件数据。

    Args:
        arc_data: TBLSTR.ARC 文件的原始字节数据。

    Returns:
        TblStrData: 解析后的数据。

    Raises:
        ValueError: 数据格式错误或解析失败。
    """
    reader = BinaryReader(arc_data)

    # 读取文件总长度
    file_len = reader.read_u32()

    items: list[Item] = []
    current_offset = 4  # file_len 之后的位置

    while not reader.is_eof():
        start_offset = current_offset

        # 读取 Item 头部
        unknown_arg = reader.read_u32()
        buf_len = reader.read_u32()

        # 读取整个缓冲区
        buf_data = reader.read_bytes(buf_len)

        # 分离字符串和剩余字节
        null_pos = buf_data.find(0x00)
        if null_pos < 0:
            raise ValueError(f"Item 缓冲区中未找到 NULL 终止符 (offset={start_offset})")

        # 字符串部分（包含 NULL）
        str_with_null = buf_data[: null_pos + 1]
        # 去除 NULL 并反转字节
        inverted_str = invert_bytes(str_with_null[:-1])
        # 解码为 CP932 字符串
        try:
            decoded_str = inverted_str.decode("cp932")
        except UnicodeDecodeError as e:
            raise ValueError(f"无法解码 CP932 字符串 (offset={start_offset}): {e}")

        # 剩余字节部分
        rest_bytes = buf_data[null_pos + 1 :]

        # 创建 Item
        item = Item(
            unknown_arg=unknown_arg,
            buf_len=buf_len,
            buf=ItemBuf(str=String(decoded_str), rest_bytes=Bytes(rest_bytes)),
            start_offset=start_offset,
        )
        items.append(item)

        # 更新当前偏移：unknown_arg(4) + buf_len(4) + buf_len
        current_offset += 8 + buf_len

    # 验证读取完毕
    if not reader.is_eof():
        raise ValueError("ARC 文件末尾存在未消费数据")

    return TblStrData(
        file_len=file_len,
        items=items,
    )


def serialize_tblstr_to_json(data: TblStrData, output_path: Path) -> None:
    """
    将 TBLSTR 数据序列化为 JSON 文件。

    Args:
        data: TBLSTR 数据。
        output_path: 输出 JSON 文件路径。

    Returns:
        None
    """
    # 转换为可序列化的字典，使用 se 函数序列化 binary.py 类型
    json_data = {
        "file_len": se(data.file_len),
        "items": [
            {
                "unknown_arg": se(item.unknown_arg),
                "buf_len": se(item.buf_len),
                "buf": {
                    "str": se(item.buf.str),
                    "rest_bytes": se(item.buf.rest_bytes),
                },
            }
            for item in data.items
        ],
    }

    write_json(output_path, json_data)


def deserialize_tblstr_from_json(input_path: Path) -> TblStrData:
    """
    从 JSON 文件反序列化 TBLSTR 数据。

    Args:
        input_path: 输入 JSON 文件路径。

    Returns:
        TblStrData: 反序列化的数据。
    """
    json_data = read_json(input_path)

    items: list[Item] = []
    # 重建 items，start_offset 将在编译时重新计算
    for item_data in json_data["items"]:
        buf_data = item_data["buf"]
        # de 函数返回 TypedValue，需要确保类型正确
        unknown_arg_val = de(item_data["unknown_arg"])
        buf_len_val = de(item_data["buf_len"])
        str_val = de(buf_data["str"])
        rest_bytes_val = de(buf_data["rest_bytes"])

        # 确保类型正确
        if not isinstance(unknown_arg_val, U32):
            raise TypeError(
                f"unknown_arg 应该是 U32 类型，实际是 {type(unknown_arg_val)}"
            )
        if not isinstance(buf_len_val, U32):
            raise TypeError(f"buf_len 应该是 U32 类型，实际是 {type(buf_len_val)}")
        if not isinstance(str_val, String):
            raise TypeError(f"str 应该是 String 类型，实际是 {type(str_val)}")
        if not isinstance(rest_bytes_val, Bytes):
            raise TypeError(
                f"rest_bytes 应该是 Bytes 类型，实际是 {type(rest_bytes_val)}"
            )

        item = Item(
            unknown_arg=unknown_arg_val,
            buf_len=buf_len_val,
            buf=ItemBuf(
                str=str_val,
                rest_bytes=rest_bytes_val,
            ),
            start_offset=0,  # 占位符，将在编译时更新
        )
        items.append(item)

    file_len_val = de(json_data["file_len"])
    if not isinstance(file_len_val, U32):
        raise TypeError(f"file_len 应该是 U32 类型，实际是 {type(file_len_val)}")

    return TblStrData(
        file_len=file_len_val,
        items=items,
    )


def decompile(input_path: PathLike, output_path: PathLike) -> None:
    """
    反编译 TBLSTR 文件：将 TBLSTR.ARC 和 TBLSTR.ARI 转换为 JSON。

    Args:
        input_path: 输入路径（可以是 .ARC 或 .ARI 文件）。
        output_path: 输出 JSON 文件路径。

    Returns:
        None

    Raises:
        ValueError: 文件格式错误或解析失败。
        FileNotFoundError: 找不到对应的配对文件。
    """
    input_path_obj = to_path(input_path)
    suffix = input_path_obj.suffix.lower()

    if suffix == ".arc":
        arc_path = input_path_obj
    else:
        raise ValueError(f"不支持的输入扩展名: {input_path_obj}，必须是 .ARC")

    if not arc_path.is_file():
        raise FileNotFoundError(f"找不到封包文件: {arc_path}")

    # 读取文件
    arc_data = arc_path.read_bytes()

    # 解析 ARC
    arc_parsed = parse_tblstr_arc(arc_data)

    # 序列化为 JSON
    output_path_obj = to_path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)

    serialize_tblstr_to_json(arc_parsed, output_path_obj)

    console.print(
        f"[OK] TBLSTR 反编译完成: {arc_path.name} -> {output_path_obj.name} "
        f"(items={len(arc_parsed.items)}",
        style="info",
    )
