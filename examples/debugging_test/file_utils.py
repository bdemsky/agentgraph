from agentgraph import FileStore
from pathlib import Path
import re
from typing import List, Tuple, Union

def parse_chat(chat) -> List[Tuple[str, str]]:
    """
    Extracts all code blocks from a chat and returns them
    as a list of (filename, codeblock) tuples.

    Parameters
    ----------
    chat : str
        The chat to extract code blocks from.

    Returns
    -------
    List[Tuple[str, str]]
        A list of tuples, where each tuple contains a filename and a code block.
    """
    # Get all ``` blocks and preceding filenames
    regex = r"(\S+)\n\s*```[^\n]*\n(.+?)```"
    matches = re.finditer(regex, chat, re.DOTALL)

    files = []
    for match in matches:
        # Strip the filename of any non-allowed characters and convert / to \
        path = re.sub(r'[\:<>"|?*]', "", match.group(1))

        # Remove leading and trailing brackets
        path = re.sub(r"^\[(.*)\]$", r"\1", path)

        # Remove leading and trailing backticks
        path = re.sub(r"^`(.*)`$", r"\1", path)

        # Remove trailing ]
        path = re.sub(r"[\]\:]$", "", path)

        # Get the code
        code = match.group(2)

        # Add the file to the list
        files.append((path, code))

    # Return the files
    return files

def read_from_fs(repo: FileStore, path: Union[str, Path], recurse = True):
    """
    Read the content at path into the repo. If path is a directory, read all files within. Only supports Unicode encoding.
    
    Parameters
    ----------
    repo: FileStore
       The file store to hold the files
    path: Union[str, Path]
       The path to read 
    recurse: bool
        Whether to recurse into subdirectories
    """
    path = Path(path).absolute()
    if path.is_dir():
        for p in path.iterdir():
            if not path.is_dir() or recurse:
                read_from_fs(repo, p)
    elif path.is_file():
        with open(path, "r") as f:
            try:
                repo[path.name] = f.read() 
            except UnicodeDecodeError as e:
                pass
                # print(f"skipped reading {str(path)} as it is not a Unicode encoded")
