import inspect
import json
import os
from pathlib import Path

from ._IdComparable import IdComparable


class InfoContainer(IdComparable):
    @staticmethod
    def unmarshall(val):
        address = val.get("Address")
        content = val.get("Content")
        refs = val.get("Refs")
        res = InfoContainer(address, content=content, refs=refs)
        return res

    @staticmethod
    def from_json(descriptor) -> "InfoContainer":
        with Path(descriptor).open() as f:
            js = json.load(f)
            address = js["Address"]
            refs = js["Refs"]
            blob_file = js["BlobFile"]
            res = InfoContainer(address, refs=refs, blob_file=blob_file, desc=descriptor)
            return res

    def __init__(self, adrr, *, refs=None, content=None, blob_file=None, desc=None):
        super(IdComparable, self).__init__()
        self.address = adrr
        self.id = IdComparable.hasher(self.address)
        self.blob_ram = content or ""  # using "" instead of None
        self.blob_file = Path(blob_file) if blob_file else ""
        self.descriptor_file = Path(desc) if desc else ""
        self.refs = list(refs) if refs else []

    def __repr__(self):
        return f"{self.Address}, {self.id}"

    @property
    def Id(self):
        return self.id

    @property
    def Address(self):
        return self.address

    @property
    def Content(self):
        return self.blob_file.read_text() if self.blob_file else self.blob_ram

    @property
    def Refs(self):
        return self.refs

    def write(self):
        if self.blob_ram:
            self.blob_file = Path().cwd() / f"{self.id}.html"
            self.blob_file.write_text(self.blob_ram)
            self.blob_file = str(self.blob_file)
            self.blob_ram = None
            self.descriptor_file = Path().cwd() / f"{self.id}.json"
            js = json.JSONEncoder()
            js = js.encode({"Address": self.Address, "Refs": self.refs, "BlobFile": self.blob_file})
            self.descriptor_file.write_text(js)

    def delete(self):
        if self.blob_file:
            Path(self.blob_file).unlink()
        if self.descriptor_file:
            Path(self.descriptor_file).unlink()

    def get_as_dict(self):
        filtered = dict(filter(lambda x: x[0][0].isupper(),
                               inspect.getmembers(self,
                                                  lambda x: not inspect.ismethod(x) and not inspect.isclass(x))))
        return filtered
