from typing import Any, Optional, Union
from pathlib import Path

class ReadFileStore:
    def __init__(self, store: 'FileStore'):
        self.filestore = store.filestore.copy()
    
    def __contains__(self, key: str) -> bool:
        return key in self.filestore

    def __getitem__(self, key: str) -> str:
        return self.filestore[key]

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __iter__(self):
        files = self.get_files()
        return files.__iter__()

    def get_files(self):
        return list(self.filestore)
        
        
class FileStore:
    def __init__(self):
        self.filestore = dict()

    def snapshot(self):
        return ReadFileStore(self)
        
    def __contains__(self, key: str) -> bool:
        return key in self.filestore

    def __getitem__(self, key: str) -> str:
        return self.filestore[key]

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __setitem__(self, key: Union[str, Path], val: str) -> None:
        if str(key).startswith("../"):
            raise ValueError(f"File name {key} attempted to access parent path.")

        assert isinstance(val, str), "val must be str"
        self.filestore[key] = val

    def __iter__(self):
        files = self.get_files()
        return files.__iter__()

    def get_files(self):
        return list(self.filestore)

    def __delitem__(self, key: Union[str, Path]) -> None:
        del self.filestore[key]
