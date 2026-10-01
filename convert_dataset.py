import argparse
import random
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert Pascal VOC XML annotations to YOLOv5 format and split into train/val/test sets."
    )
    parser.add_argument(
        "--source-dir",
        type=str,
        default=None,
        help="Path to the raw dataset folder. Defaults to sohas_weapons_dataset or Sohas_weapon-Detection under the script directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="dataset_yolo",
        help="Directory where the YOLO dataset will be created.",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.70,
        help="Train split ratio. Default: 0.70.",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Validation split ratio. Default: 0.15.",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Test split ratio. Default: 0.15.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed used for reproducible splitting.",
    )
    return parser.parse_args()


def resolve_dataset_dir(script_dir: Path, source_dir: str | None = None) -> Path:
    if source_dir:
        path = Path(source_dir).expanduser()
        if not path.is_absolute():
            path = (script_dir / path).resolve()
        if path.exists():
            return path
        raise FileNotFoundError(f"Source dataset not found: {path}")

    candidates = [
        script_dir / "sohas_weapons_dataset",
        script_dir / "Sohas_weapon-Detection",
        script_dir / "sohas_dataset",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No dataset folder found. Please create a folder named 'sohas_weapons_dataset' or 'Sohas_weapon-Detection' "
        "or pass --source-dir explicitly."
    )


def collect_xml_files(annotation_dir: Path):
    if not annotation_dir.exists():
        return []

    xml_files = []
    for path in annotation_dir.rglob("*.xml"):
        if path.is_file():
            xml_files.append(path)
    return sorted(xml_files)


def find_matching_image(image_dir: Path, xml_file: Path) -> Path | None:
    stem = xml_file.stem
    for ext in sorted(SUPPORTED_EXTENSIONS, key=lambda e: (e != ".jpg", e != ".jpeg", e)):
        match = next(image_dir.rglob(f"{stem}{ext}"), None)
        if match is not None:
            return match

    for match in image_dir.rglob("*"):
        if match.is_file() and match.stem == stem and match.suffix.lower() in SUPPORTED_EXTENSIONS:
            return match

    return None


def collect_dataset_items(dataset_root: Path):
    items = []

    train_image_dir = dataset_root / "images"
    train_annotation_dir = dataset_root / "annotations"
    test_image_dir = dataset_root / "images_test"
    test_annotation_dir = dataset_root / "annotations_test"

    train_xmls = collect_xml_files(train_annotation_dir)
    if not train_xmls and (train_annotation_dir / "xmls").exists():
        train_xmls = collect_xml_files(train_annotation_dir / "xmls")

    for xml_file in train_xmls:
        image_path = find_matching_image(train_image_dir, xml_file)
        if image_path is not None:
            items.append({
                "split": "train",
                "image_path": image_path,
                "xml_path": xml_file,
            })

    test_xmls = collect_xml_files(test_annotation_dir)
    if not test_xmls and (test_annotation_dir / "xmls").exists():
        test_xmls = collect_xml_files(test_annotation_dir / "xmls")

    for xml_file in test_xmls:
        image_path = find_matching_image(test_image_dir, xml_file)
        if image_path is not None:
            items.append({
                "split": "test",
                "image_path": image_path,
                "xml_path": xml_file,
            })

    return items


def parse_xml_annotations(xml_path: Path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    width = 0.0
    height = 0.0
    size = root.find("size")
    if size is not None:
        width = float(size.findtext("width", "0") or 0)
        height = float(size.findtext("height", "0") or 0)

    objects = []
    for obj in root.findall("object"):
        name = (obj.findtext("name") or "").strip()
        if not name:
            continue

        bnd = obj.find("bndbox")
        if bnd is None:
            continue

        try:
            xmin = float(bnd.findtext("xmin", "0") or 0)
            ymin = float(bnd.findtext("ymin", "0") or 0)
            xmax = float(bnd.findtext("xmax", "0") or 0)
            ymax = float(bnd.findtext("ymax", "0") or 0)
        except ValueError:
            continue

        if width <= 0 or height <= 0:
            continue

        x_center = ((xmin + xmax) / 2.0) / width
        y_center = ((ymin + ymax) / 2.0) / height
        box_w = (xmax - xmin) / width
        box_h = (ymax - ymin) / height

        if box_w <= 0 or box_h <= 0:
            continue

        objects.append({
            "class_name": name,
            "x_center": x_center,
            "y_center": y_center,
            "width": box_w,
            "height": box_h,
        })

    return objects


def ensure_dirs(output_dir: Path):
    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)


def write_data_yaml(output_dir: Path, class_names):
    yaml_path = output_dir / "data.yaml"
    yaml_data = {
        "path": "./dataset_yolo",
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "nc": len(class_names),
        "names": class_names,
    }

    if yaml is not None:
        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_data, f, sort_keys=False, default_flow_style=False)
    else:
        content = (
            "path: ./dataset_yolo\n"
            "train: images/train\n"
            "val: images/val\n"
            "test: images/test\n"
            f"nc: {len(class_names)}\n"
            f"names: {class_names}\n"
        )
        with open(yaml_path, "w", encoding="utf-8") as f:
            f.write(content)

    return yaml_path


def split_items(items, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=42):
    if abs((train_ratio + val_ratio + test_ratio) - 1.0) > 1e-6:
        raise ValueError("Train, val, and test ratios must sum to 1.0.")

    rng = random.Random(seed)
    shuffled = items[:]
    rng.shuffle(shuffled)

    total = len(shuffled)
    n_train = int(round(total * train_ratio))
    n_val = int(round(total * val_ratio))
    n_test = total - n_train - n_val

    if n_test < 0:
        n_val = max(0, total - n_train)
        n_test = total - n_train - n_val

    if n_train == 0 and total > 0:
        n_train = 1
        n_val = max(0, int(round(total * val_ratio)))
        n_test = total - n_train - n_val

    train_items = shuffled[:n_train]
    remaining = shuffled[n_train:]

    if n_val > len(remaining):
        n_val = len(remaining)

    val_items = remaining[:n_val]
    test_items = remaining[n_val:]

    return train_items, val_items, test_items


def generate_labels_for_split(output_dir: Path, image_dir: Path, label_dir: Path, split_name: str, split_items, class_to_id):
    for item in split_items:
        image_path = item["image_path"]
        xml_path = item["xml_path"]

        if not image_path.exists():
            continue
        relative_image_name = image_path.name

        dest_image = image_dir / relative_image_name
        shutil.copy2(image_path, dest_image)

        label_path = label_dir / f"{image_path.stem}.txt"
        with open(label_path, "w", encoding="utf-8") as f:
            for ann in parse_xml_annotations(xml_path):
                class_id = class_to_id.get(ann["class_name"])
                if class_id is None:
                    continue
                f.write(
                    f"{class_id} {ann['x_center']:.6f} {ann['y_center']:.6f} "
                    f"{ann['width']:.6f} {ann['height']:.6f}\n"
                )


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    dataset_root = resolve_dataset_dir(script_dir, args.source_dir)
    output_dir = (script_dir / args.output_dir).resolve()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ensure_dirs(output_dir)

    train_items = []
    test_items = []

    train_image_dir = dataset_root / "images"
    train_annotation_dir = dataset_root / "annotations"
    test_image_dir = dataset_root / "images_test"
    test_annotation_dir = dataset_root / "annotations_test"

    if train_image_dir.exists() and train_annotation_dir.exists():
        train_xmls = collect_xml_files(train_annotation_dir)
        if not train_xmls and (train_annotation_dir / "xmls").exists():
            train_xmls = collect_xml_files(train_annotation_dir / "xmls")

        for xml_file in train_xmls:
            image_path = find_matching_image(train_image_dir, xml_file)
            if image_path is not None:
                train_items.append({"image_path": image_path, "xml_path": xml_file})

    if test_image_dir.exists() and test_annotation_dir.exists():
        test_xmls = collect_xml_files(test_annotation_dir)
        if not test_xmls and (test_annotation_dir / "xmls").exists():
            test_xmls = collect_xml_files(test_annotation_dir / "xmls")

        for xml_file in test_xmls:
            image_path = find_matching_image(test_image_dir, xml_file)
            if image_path is not None:
                test_items.append({"image_path": image_path, "xml_path": xml_file})

    if not train_items and not test_items:
        raise FileNotFoundError(f"No Pascal VOC XML annotations found in dataset: {dataset_root}")

    all_classes = set()
    for item in train_items + test_items:
        for ann in parse_xml_annotations(item["xml_path"]):
            all_classes.add(ann["class_name"])

    if not all_classes:
        raise ValueError(f"No object classes were found in the XML annotations under {dataset_root}")

    class_names = sorted(all_classes)
    class_to_id = {name: idx for idx, name in enumerate(class_names)}

    if test_items:
        train_split, val_split, _ = split_items(
            train_items,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )
        final_test_items = test_items
    else:
        train_split, val_split, final_test_items = split_items(
            train_items,
            train_ratio=args.train_ratio,
            val_ratio=args.val_ratio,
            test_ratio=args.test_ratio,
            seed=args.seed,
        )

    generate_labels_for_split(output_dir, output_dir / "images" / "train", output_dir / "labels" / "train", "train", train_split, class_to_id)
    generate_labels_for_split(output_dir, output_dir / "images" / "val", output_dir / "labels" / "val", "val", val_split, class_to_id)
    generate_labels_for_split(output_dir, output_dir / "images" / "test", output_dir / "labels" / "test", "test", final_test_items, class_to_id)

    write_data_yaml(output_dir, class_names)

    print(f"Dataset root: {dataset_root}")
    print(f"Output directory: {output_dir}")
    print(f"Classes detected: {class_names}")
    print(f"Train samples: {len(train_split)}")
    print(f"Val samples: {len(val_split)}")
    print(f"Test samples: {len(final_test_items)}")
    print(f"YOLO data.yaml created at: {output_dir / 'data.yaml'}")


if __name__ == "__main__":
    main()
