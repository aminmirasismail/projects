"""Label separator study: the bin's front label engraved with each house separator.

  uv run --no-project --python 3.13 --with bpy --with trimesh --with networkx --with lxml \
      python sep_study.py [--preview]
Writes renders/sep_<variant>.jpg (close-ups) and prints each label's size.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import purge_bin as P  # noqa: E402

S = P.S


def main():
    preview = "--preview" in sys.argv
    out = os.path.join(HERE, "renders", "_preview" if preview else "")
    os.makedirs(out, exist_ok=True)
    m = 0.001
    for sep in S.SEPARATORS:
        P.SEP = sep
        shell, base, box, extras = P.build()
        print(f"{sep}: label {box[2] - box[0]:.1f} x {box[3] - box[1]:.1f} mm")
        S.to_studio([shell, base] + extras)
        S.studio(samples=16 if preview else 128, res=(800, 600) if preview else (1400, 1050))
        S.camera((-0.035, -0.16, 0.058), target=(0, -P.D / 2 * m, P.LABEL_Z * m), lens=105)
        png = os.path.join(out, f"sep_{sep}.png")
        S.render(png)
        from PIL import Image
        Image.open(png).convert("RGB").save(png[:-4] + ".jpg", quality=90)
        os.remove(png)


if __name__ == "__main__":
    main()
