import time
from pathlib import Path

from OpenSSL import crypto


def generate_ca_certificate(cn,key_size=2048):
    # generate a certifcate signed by a CA
    # generate a self signed certificate
    # generate a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, key_size)
    # generate a certificate request
    req = crypto.X509Req()
    req.set_pubkey(key)
    # set the subject
    req.get_subject().CN = cn
    req.get_subject().O = "Discraper"
    req.get_subject().OU = "Discraper"
    req.get_subject().C = "DE"

    # set the Basic Restrictions
    req.add_extensions([
        crypto.X509Extension(b"basicConstraints", True, b"CA:TRUE"),
        crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
    ])

    # sign the request with the key
    req.sign(key, "sha256")
    # generate a certificate
    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(time.time_ns() * time.time_ns())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(1 * 365 * 24 * 60 * 60)
    cert.set_issuer(req.get_subject())
    cert.set_subject(req.get_subject())
    cert.add_extensions(req.get_extensions())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(key, "sha256")

    return cert, key


def generate_certificate(CN, ca_cert, ca_key,key_size=2048):
    # generate a certificate signed by other CA
    # generate a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, key_size)
    # generate a certificate request
    req = crypto.X509Req()
    req.set_pubkey(key)
    # set the subject
    req.get_subject().CN = CN
    req.get_subject().O = "Discraper"
    req.get_subject().OU = "Discraper"
    # req.get_subject().C = "DE"
    # set the Basic Restrictions
    req.add_extensions([
    # add alternative names
        crypto.X509Extension(b"subjectAltName", False, b"DNS:localhost, IP:127.0.0.1"),
        crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
        crypto.X509Extension(b"keyUsage", True, b"digitalSignature, keyEncipherment"),
    ])

    # sign the request with the key
    req.sign(key, "sha256")
    # generate a certificate
    cert = crypto.X509()
    cert.set_version(2)
    cert.set_serial_number(time.time_ns() * time.time_ns())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(1 * 365 * 24 * 60 * 60)
    cert.set_issuer(ca_cert.get_subject())
    cert.set_subject(req.get_subject())
    cert.add_extensions(req.get_extensions())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(ca_key, "sha256")
    return cert, key


# save the certificate to a file
def save_certificate(filename, cert, key=None):
    # save the certificate
    cert_path = Path.cwd() / Path(filename + ".crt")
    key_path = None
    cert_path.unlink(missing_ok=True)
    cert_file = open(filename + ".crt", "wb")
    cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    cert_file.close()
    if key is not None:
        # save the private key
        key_path = Path.cwd() / Path(filename + ".key")
        key_path.unlink(missing_ok=True)
        key_file = open(filename + ".key", "wb")
        key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
        key_file.close()
    return cert_path, key_path


## test -----------------------------------------------------------------------
if __name__ == "__main__":
    cacert, cakey = generate_ca_certificate("DISCRAPPER CA")
    save_certificate("discraper_ca", cacert, cakey)
    endcert, endkey = generate_certificate("DISCRAPPER END1", cacert, cakey)
    save_certificate("discraper_end1", endcert, endkey)
    endcert, endkey = generate_certificate("DISCRAPPER END2", cacert, cakey)
    save_certificate("discraper_end2", endcert, endkey)
