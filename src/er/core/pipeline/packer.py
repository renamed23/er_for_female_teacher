from er.utils.console import console
from er.utils.fs import PathLike, to_path


def unpack(input_path: PathLike, out_dir: PathLike) -> None:
    """
    解包。

    Args:
        input_path: 输入包路径。
        out_dir: 解包输出目录。

    Returns:
        None
    """
    source = to_path(input_path)
    output_dir = to_path(out_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # TODO

    console.print(
        f"[OK] unpack 完成: {source} -> {output_dir}",
        style="info",
    )


def pack(input_dir: PathLike, out_path: PathLike) -> None:
    """
    将目录内容重新打包。

    Args:
        input_dir: 输入目录路径。
        out_path: 输出包路径。

    Returns:
        None

    Raises:
        ValueError: 输入非法、命名冲突或字段超限。
    """
    input_root = to_path(input_dir)
    output_path = to_path(out_path)
    if not input_root.is_dir():
        raise ValueError(f"输入目录不存在: {input_root}")

    # TODO

    console.print(
        f"[OK] pack 完成: {input_root} -> {output_path}",
        style="info",
    )
