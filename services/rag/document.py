from dataclasses import dataclass


@dataclass
class Document:

    document_id: str

    title: str

    content: str
