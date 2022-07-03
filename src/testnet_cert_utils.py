import time

from OpenSSL import crypto


def generate_ca_certificate(cn):
    # generate a certifcate signed by a CA
    # generate a self signed certificate
    # generate a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
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
    cert.set_version(3)
    cert.set_serial_number(time.time_ns() * time.time_ns())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(req.get_subject())
    cert.set_subject(req.get_subject())
    cert.add_extensions(req.get_extensions())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(key, "sha256")

    return cert, key


def generate_certificate(CN, ca_cert, ca_key):
    # generate a certificate signed by other CA
    # generate a key pair
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
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
        crypto.X509Extension(b"basicConstraints", True, b"CA:FALSE"),
        # crypto.X509Extension(b"keyUsage", True, b"keyCertSign, cRLSign"),
    ])

    # sign the request with the key
    req.sign(key, "sha256")
    # generate a certificate
    cert = crypto.X509()
    cert.set_version(3)
    cert.set_serial_number(time.time_ns()*time.time_ns())
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(10 * 365 * 24 * 60 * 60)
    cert.set_issuer(ca_cert.get_subject())
    cert.set_subject(req.get_subject())
    cert.add_extensions(req.get_extensions())
    cert.set_pubkey(req.get_pubkey())
    cert.sign(ca_key, "sha256")
    return cert, key


# save the certificate to a file
def save_certificate(cert, key, filename):
    # save the private key
    key_file = open(filename + ".key", "wb")
    key_file.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))
    key_file.close()
    # save the certificate
    cert_file = open(filename + ".crt", "wb")
    cert_file.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    cert_file.close()
    return cert, key



## test -----------------------------------------------------------------------
if __name__ == "__main__":
    cacert, cakey = generate_ca_certificate("DISCRAPPER CA")
    save_certificate(cacert, cakey, "discraper_ca")
    endcert, endkey = generate_certificate("DISCRAPPER END1", cacert, cakey)
    save_certificate(endcert, endkey, "discraper_end1")
    endcert, endkey = generate_certificate("DISCRAPPER END2", cacert, cakey)
    save_certificate(endcert, endkey, "discraper_end2")
