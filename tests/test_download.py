import gzip
import json

import pytest

from damir.download import download


class Response:
    def __init__(self, body=b"", text="", length=None):
        self.body = body
        self.text = text
        self.headers = {"Content-Length": str(len(body) if length is None else length)}

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        yield self.body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def session(monkeypatch, payload, length=None):
    calls = []
    class Session:
        def __init__(self):
            self.headers = {}

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url, **kwargs):
            calls.append(url)
            if "download.php?" in url:
                return Response(text='<a href="download_file.php?file=Open_DAMIR/A202501.csv.gz&amp;token=test">Fichier</a>')
            return Response(payload, length=length)
    monkeypatch.setattr("damir.download.requests.Session", Session)
    return calls


def test_download_session_and_replay(tmp_path, monkeypatch):
    payload = gzip.compress(b"a;b\n1;2\n")
    calls = session(monkeypatch, payload)
    path = download(tmp_path, "202501")
    assert path.read_bytes() == payload
    assert len(calls) == 2
    assert "&token=test" in calls[1]
    download(tmp_path, "202501")
    assert len(calls) == 2
    meta = json.loads(path.with_suffix(path.suffix + ".json").read_text())
    assert "token" not in str(meta)


def test_html_refusal_is_not_published(tmp_path, monkeypatch):
    session(monkeypatch, b"<html>Refus</html>")
    with pytest.raises(ValueError, match="gzip"):
        download(tmp_path, "202501")
    assert not (tmp_path / "data/raw/A202501.csv.gz").exists()


def test_incomplete_transfer_is_not_published(tmp_path, monkeypatch):
    session(monkeypatch, gzip.compress(b"a;b\n"), length=9999)
    with pytest.raises(ValueError, match="incomplet"):
        download(tmp_path, "202501")
    assert not (tmp_path / "data/raw/A202501.csv.gz").exists()
