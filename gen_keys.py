from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime

# Generate private key
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

# Set subject/issuer details
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
    x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, "LANtern"),
    x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
])

# Build certificate
cert = x509.CertificateBuilder() \
    .subject_name(subject) \
    .issuer_name(issuer) \
    .public_key(key.public_key()) \
    .serial_number(x509.random_serial_number()) \
    .not_valid_before(datetime.datetime.utcnow()) \
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365)) \
    .add_extension(x509.SubjectAlternativeName([
        x509.DNSName("localhost"),
        x509.DNSName("192.168.100.21"),   # <-- Replace with your server's actual IP
    ]), critical=False) \
    .sign(key, hashes.SHA256())

# Write cert and key
with open("cert.pem", "wb") as f:
    f.write(cert.public_bytes(serialization.Encoding.PEM))

with open("key.pem", "wb") as f:
    f.write(key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    ))

print("✅ cert.pem and key.pem generated.")