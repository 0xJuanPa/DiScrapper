import json
from pathlib import Path

from ._IdComparable import IdComparable


class InfoContainer(IdComparable):
    @staticmethod
    def unmarshall(val):
        res = val.get("Address")
        res = InfoContainer(res)
        return res

    def __init__(self, adrr, *, refs=None, content=None, file=None, desc=None):
        super(IdComparable, self).__init__()
        self.address = adrr
        self.id = IdComparable.hasher(self.address)
        self.blob_ram = content or ""  # using "" instead of None
        self.blob_file = Path(file) if file else ""
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

    def write(self, path):
        if self.blob_ram:
            self.blob_file = Path(path / f"{self.id}.html")
            self.blob_file.write_text(self.blob_ram)
            self.blob_ram = None
            self.descriptor_file = Path(path / f"{self.id}.json")
            js = json.JSONEncoder()
            js = js.encode({"Title": self.Address, "Refs": self.refs, "BlobFile": self.blob_file})
            self.descriptor_file.write_text(js)

    def delete(self):
        if self.blob_file:
            self.blob_file.unlink()
        if self.descriptor_file:
            self.descriptor_file.unlink()
