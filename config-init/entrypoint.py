import base64
import hashlib
import os
import random
import string
import uuid
from pprint import pprint

import click
import consulate
from M2Crypto.EVP import Cipher


# Default charset
_DEFAULT_CHARS = "".join([string.ascii_uppercase,
                          string.digits,
                          string.lowercase])


def get_random_chars(size=12, chars=_DEFAULT_CHARS):
    """Generates random characters.
    """
    return ''.join(random.choice(chars) for _ in range(size))


def ldap_encode(password):
    # borrowed from community-edition-setup project
    # see http://git.io/vIRex
    salt = os.urandom(4)
    sha = hashlib.sha1(password)
    sha.update(salt)
    b64encoded = '{0}{1}'.format(sha.digest(), salt).encode('base64').strip()
    encrypted_password = '{{SSHA}}{0}'.format(b64encoded)
    return encrypted_password


def get_quad():
    # borrowed from community-edition-setup project
    # see http://git.io/he1p
    return str(uuid.uuid4())[:4].upper()


def encrypt_text(text, key):
    # Porting from pyDes-based encryption (see http://git.io/htxa)
    # to use M2Crypto instead (see https://gist.github.com/mrluanma/917014)
    cipher = Cipher(alg="des_ede3_ecb",
                    key=b"{}".format(key),
                    op=1,
                    iv="\0" * 16)
    encrypted_text = cipher.update(b"{}".format(text))
    encrypted_text += cipher.final()
    return base64.b64encode(encrypted_text)


def decrypt_text(encrypted_text, key):
    # Porting from pyDes-based encryption (see http://git.io/htpk)
    # to use M2Crypto instead (see https://gist.github.com/mrluanma/917014)
    cipher = Cipher(alg="des_ede3_ecb",
                    key=b"{}".format(key),
                    op=0,
                    iv="\0" * 16)
    decrypted_text = cipher.update(base64.b64decode(
        b"{}".format(encrypted_text)
    ))
    decrypted_text += cipher.final()
    return decrypted_text


def reindent(text, num_spaces=1):
    text = [(num_spaces * " ") + line.lstrip() for line in text.splitlines()]
    text = "\n".join(text)
    return text


def generate_base64_contents(text, num_spaces=1):
    text = text.encode("base64").strip()
    if num_spaces > 0:
        text = reindent(text, num_spaces)
    return text


def get_sys_random_chars(size=12, chars=_DEFAULT_CHARS):
    """Generates random characters based on OS.
    """
    return ''.join(random.SystemRandom().choice(chars) for _ in range(size))


def join_quad_str(x):
    return ".".join([get_quad() for _ in xrange(x)])


def safe_inum_str(x):
    return x.replace("@", "").replace("!", "").replace(".", "")


def encode_template(fn, ctx, base_dir="/opt/config-init/templates"):
    path = os.path.join(base_dir, fn)
    with open(path) as f:
        return generate_base64_contents(f.read() % ctx)


def generate_config(admin_pw, email, domain, org_name):
    cfg = {}
    cfg["encoded_salt"] = get_random_chars(24)
    cfg["encoded_ldap_pw"] = ldap_encode(admin_pw)
    cfg["encoded_ox_ldap_pw"] = encrypt_text(admin_pw, cfg["encoded_salt"])
    cfg["orgName"] = org_name
    cfg["hostname"] = domain
    cfg["admin_email"] = email
    cfg["ldap_hostname"] = "N/A"
    cfg["ldapPassFn"] = "N/A"
    cfg["ldap_port"] = 1389
    cfg["ldap_admin_port"] = 4444
    cfg["ldap_jmx_port"] = 1689
    cfg["ldap_binddn"] = cfg["opendj_ldap_binddn"] = "cn=directory manager"
    cfg["ldaps_port"] = 1636
    cfg["ldap_backend_type"] = "je"
    cfg["jetty_base"] = "/opt/gluu/jetty"
    cfg["baseInum"] = "@!{}".format(join_quad_str(4))
    cfg["inumOrg"] = "{}!0001!{}".format(cfg["baseInum"], join_quad_str(2))
    cfg["inumOrgFN"] = safe_inum_str(cfg["inumOrg"])

    cfg["inumAppliance"] = "{}!0002!{}".format(
        cfg["baseInum"], join_quad_str(2))

    cfg["inumApplianceFN"] = safe_inum_str(cfg["inumAppliance"])

    cfg["oxauth_client_id"] = "{}!0008!{}".format(
        cfg["inumOrg"], join_quad_str(2))

    cfg["oxauthClient_encoded_pw"] = encrypt_text(
        get_random_chars(), cfg["encoded_salt"])

    cfg["scim_rs_client_id"] = "{}!0008!{}".format(
        cfg["inumOrg"], join_quad_str(2))

    cfg["scim_rp_client_id"] = "{}!0008!{}".format(
        cfg["inumOrg"], join_quad_str(2))

    cfg["passport_rs_client_id"] = "{}!0008!{}".format(
        cfg["inumOrg"], join_quad_str(2))

    cfg["passport_rp_client_id"] = "{}!0008!{}".format(
        cfg["inumOrg"], join_quad_str(2))

    cfg["passport_rp_client_cert_fn"] = "/etc/certs/passport-rp.pem"
    cfg["passport_rp_client_cert_alg"] = "RS512"

    cfg["pairwiseCalculationKey"] = get_sys_random_chars(
        random.randint(20, 30))

    cfg["pairwiseCalculationSalt"] = get_sys_random_chars(
        random.randint(20, 30))

    cfg["default_openid_jks_dn_name"] = "CN=oxAuth CA Certificates"
    cfg["oxauth_openid_jks_fn"] = "/etc/certs/oxauth-keys.jks"
    cfg["oxauth_openid_jks_pass"] = get_random_chars()
    cfg["shibJksFn"] = "/etc/certs/shibIDP.jks"
    cfg["shibJksPass"] = get_random_chars()
    cfg["oxTrustConfigGeneration"] = "false"

    cfg["encoded_shib_jks_pw"] = encrypt_text(
        cfg["shibJksPass"], cfg["encoded_salt"])

    cfg["scim_rs_client_jks_fn"] = "/etc/certs/scim-rs.jks"
    cfg["scim_rs_client_jks_pass"] = get_random_chars()

    cfg["scim_rs_client_jks_pass_encoded"] = encrypt_text(
        cfg["scim_rs_client_jks_pass"], cfg["encoded_salt"])

    cfg["passport_rs_client_jks_fn"] = "/etc/certs/passport-rs.jks"
    cfg["passport_rs_client_jks_pass"] = get_random_chars()

    cfg["passport_rs_client_jks_pass_encoded"] = encrypt_text(
        cfg["passport_rs_client_jks_pass"], cfg["encoded_salt"])

    cfg["shibboleth_version"] = "v3"
    cfg["idp3Folder"] = "/opt/shibboleth-idp"
    cfg["ldap_site_binddn"] = "cn=directory manager,o=site"

    cfg["oxauth_config_base64"] = encode_template(
        "oxauth-config.json", cfg)

    cfg["oxauth_static_conf_base64"] = encode_template(
        "oxauth-static-conf.json", cfg)

    cfg["oxauth_error_base64"] = encode_template("oxauth-errors.json", cfg)
    cfg["oxtrust_config_base64"] = encode_template("oxtrust-config.json", cfg)

    cfg["oxtrust_cache_refresh_base64"] = encode_template(
        "oxtrust-cache-refresh.json", cfg)

    cfg["oxtrust_import_person_base64"] = encode_template(
        "oxtrust-import-person.json", cfg)

    cfg["oxidp_config_base64"] = encode_template("oxidp-config.json", cfg)
    cfg["oxcas_config_base64"] = encode_template("oxcas-config.json", cfg)

    cfg["oxasimba_config_base64"] = encode_template(
        "oxasimba-config.json", cfg)

    # TODO:
    # "oxauth_openid_key_base64"
    # "scim_rs_client_base64_jwks"
    # "scim_rp_client_base64_jwks"
    # "passport_rs_client_base64_jwks"
    # "passport_rp_client_base64_jwks"
    # "passport_rp_client_cert_alias" # MUST get 'kid' of passport RP JWKS
    return cfg


def main(admin_pw="admin", email="support@gluu.example.com",
         domain="gluu.example.com", org_name="Gluu",
         kv_host="localhost", kv_port=8500):
    cfg = generate_config(admin_pw, email, domain, org_name)
    pprint(cfg)

    consul = consulate.Consul(host=kv_host, port=kv_port)

    for k, v in cfg.iteritems():
        if k in consul.kv:
            click.echo("{!r} config already exists ... skipping".format(k))
            continue

        click.echo("setting {!r} config".format(k))
        consul.kv.set(k, v)


@click.command()
@click.option("--admin-pw",
              default="admin",
              help="Password for admin access.",
              show_default=True)
@click.option("--email",
              default="support@gluu.example.com",
              help="Email for support.",
              show_default=True)
@click.option("--domain",
              default="gluu.example.com",
              help="Domain for Gluu Server.",
              show_default=True)
@click.option("--org-name",
              default="Gluu",
              help="Organization name.",
              show_default=True)
@click.option("--kv-host",
              default="localhost",
              help="Hostname/IP address of KV store.",
              show_default=True)
@click.option("--kv-port",
              default=8500,
              help="Port of KV store.",
              show_default=True)
def cli(admin_pw, email, domain, org_name, kv_host, kv_port):
    main(admin_pw, email, domain, org_name, kv_host, kv_port)


if __name__ == "__main__":
    cli()
