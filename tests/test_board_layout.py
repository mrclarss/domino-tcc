import shutil
import subprocess
from pathlib import Path


def test_cadeia_dobra_na_borda_da_mesa():
    node = shutil.which("node")
    assert node, "node é necessário para conferir o layout da mesa"
    script = Path(__file__).with_name("test_board_layout.mjs")
    subprocess.run([node, "--test", str(script)], check=True)
