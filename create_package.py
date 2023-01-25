"""Prepares server package from addon repo to upload to server.

Requires Python 3.9. (Or at least 3.8+).

This script should be called from cloned addon repo.

It will produce 'package' subdirectory which could be pasted into server
addon directory directly (eg. into `openpype4-backend/addons`).

Format of package folder:
ADDON_REPO/package/{addon name}/{addon version}

You can specify `--output_dir` in arguments to change output directory where
package will be created. Existing package directory will be always purged if
already present! This could be used to create package directly in server folder
if available.

Package contains server side files directly,
client side code zipped in `private` subfolder.
"""

import os
import sys
import re
import shutil
import argparse
import logging
import collections

ADDON_NAME = "shotgrid"

# Files or directories that won't be copied to server part of addon
SERVER_ADDON_SUBPATHS = {
    "frontend",
    "private",
    "public",
    "services",
    "settings",
    "__init__.py",
    "version.py",
}

# Patterns of directories to be skipped for server part of addon
IGNORE_DIR_PATTERNS = [
    re.compile(pattern)
    for pattern in {
        # Skip directories starting with '.'
        r"^\.",
        # Skip any pycache folders
        "^__pycache__$"
    }
]

# Patterns of files to be skipped for server part of addon
IGNORE_FILE_PATTERNS = [
    re.compile(pattern)
    for pattern in {
        # Skip files starting with '.'
        # NOTE this could be an issue in some cases
        r"^\.",
        # Skip '.pyc' files
        r"\.pyc$"
    }
]


def safe_copy_file(src_path, dst_path):
    """Copy file and make sure destination directory exists.

    Ignore if destination already contains directories from source.

    Args:
        src_path (str): File path that will be copied.
        dst_path (str): Path to destination file.
    """

    if src_path == dst_path:
        return

    dst_dir = os.path.dirname(dst_path)
    try:
        os.makedirs(dst_dir)
    except Exception:
        pass

    shutil.copy2(src_path, dst_path)


def _value_match_regexes(value, regexes):
    for regex in regexes:
        if regex.search(value):
            return True
    return False


def find_files_in_subdir(
    src_path,
    ignore_file_patterns=None,
    ignore_dir_patterns=None
):
    if ignore_file_patterns is None:
        ignore_file_patterns = IGNORE_FILE_PATTERNS

    if ignore_dir_patterns is None:
        ignore_dir_patterns = IGNORE_DIR_PATTERNS
    output = []

    hierarchy_queue = collections.deque()
    hierarchy_queue.append((src_path, []))
    while hierarchy_queue:
        item = hierarchy_queue.popleft()
        dirpath, parents = item
        for name in os.listdir(dirpath):
            path = os.path.join(dirpath, name)
            if os.path.isfile(path):
                if not _value_match_regexes(name, ignore_file_patterns):
                    items = list(parents)
                    items.append(name)
                    output.append((path, os.path.sep.join(items)))
                continue

            if not _value_match_regexes(name, ignore_dir_patterns):
                items = list(parents)
                items.append(name)
                hierarchy_queue.append((path, items))

    return output


def copy_server_content(addon_output_dir, current_dir, log):
    """Copies server side folders to 'addon_package_dir'

    Args:
        addon_output_dir (str): package dir in addon repo dir
        current_dir (str): addon repo dir
        log (logging.Logger)
    """

    log.info("Copying server content")

    shutil.copytree(
        os.path.join(current_dir, "server"),
        addon_output_dir
    )

    shutil.copy2(
        os.path.join(current_dir, "version.py"),
        addon_output_dir
    )


def zip_client_side(addon_package_dir, current_dir, zip_file_name, log):
    """Copy and zip `client` content into `addon_package_dir'.

    Args:
        addon_package_dir (str): Output package directory path.
        current_dir (str): Directoy path of addon source.
        zip_file_name (str): Output zip file name in format
            '{ADDON_NAME}_{ADDON_VERSION}'.
        log (logging.Logger): Logger object.
    """

    client_dir = os.path.join(current_dir, "client")
    if not os.path.isdir(client_dir):
        log.info("Client directory was not found. Skipping")
        return

    log.info("Preparing client code zip")
    private_dir = os.path.join(addon_package_dir, "private")
    temp_dir_to_zip = os.path.join(private_dir, "temp")
    # shutil.copytree expects glob-style patterns, not regex
    zip_dir_path = os.path.join(temp_dir_to_zip, zip_file_name)
    for path, sub_path in find_files_in_subdir(client_dir):
        safe_copy_file(path, os.path.join(zip_dir_path, sub_path))

    toml_path = os.path.join(client_dir, "pyproject.toml")
    if os.path.exists(toml_path):
        shutil.copy(toml_path, private_dir)

    zip_file_path = os.path.join(os.path.join(private_dir, zip_file_name))
    shutil.make_archive(zip_file_path, "zip", temp_dir_to_zip)
    shutil.rmtree(temp_dir_to_zip)


def main(output_dir=None):
    log = logging.getLogger("create_package")
    log.info("Start creating package")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    if not output_dir:
        output_dir = os.path.join(current_dir, "package")

    version_filepath = os.path.join(current_dir, "version.py")
    version_content = {}
    with open(version_filepath, "r") as stream:
        exec(stream.read(), version_content)
    addon_version = version_content["__version__"]

    new_created_version_dir = os.path.join(
        output_dir, ADDON_NAME, addon_version
    )
    if os.path.isdir(new_created_version_dir):
        log.info(f"Purging {new_created_version_dir}")
        shutil.rmtree(output_dir)

    log.info(f"Preparing package for {ADDON_NAME}-{addon_version}")

    zip_file_name = f"{ADDON_NAME}_{addon_version}"
    addon_output_dir = os.path.join(output_dir, ADDON_NAME, addon_version)

    if os.path.exists(addon_output_dir):
        os.rmdir(addon_output_dir)

    copy_server_content(addon_output_dir, current_dir, log)

    zip_client_side(addon_output_dir, current_dir, zip_file_name, log)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output_dir",
        help=(
            "Directory path where package will be created"
            " (Will be purged if already exists!)"
        )
    )

    args = parser.parse_args(sys.argv[1:])
    main(args.output_dir)
