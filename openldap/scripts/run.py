import os
import re
import subprocess
import glob
import tempfile
import shutil
import traceback

import consulate


GLUU_KV_HOST = os.environ.get('GLUU_KV_HOST', 'localhost')
GLUU_KV_PORT = os.environ.get('GLUU_KV_PORT', 8500)
GLUU_LDAP_HOSTNAME = os.environ.get('GLUU_LDAP_HOSTNAME', 'localhost')
# TODO env var acesslog_comentout
TMPDIR = tempfile.mkdtemp()


consul = consulate.Consul(host=GLUU_KV_HOST, port=GLUU_KV_PORT)


# START functions taken from setup.py
def fomatWithDict(text, dictionary):
    text = re.sub(r"%([^\(])", r"%%\1", text)
    text = re.sub(r"%$", r"%%", text)  # There was a % at the end?
    return text % dictionary


def commentOutText(text):
    textLines = text.split('\n')
    lines = []
    for textLine in textLines:
        lines.append('#%s' % textLine)
    return "\n".join(lines)


def runcmd(args, cwd=None, env=None, useWait=False):
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=env)
        if useWait:
            code = p.wait()
            print 'Run: %s with result code: %d' % (' '.join(args), code)
        else:
            output, err = p.communicate()
            if output:
                print output
            if err:
                print err
    except:
        print "Error running command : %s" % " ".join(args)
        print traceback.format_exc()
# END functions taken from setup.py


def set_kv():
    consul.kv.set('ldap_hostname', GLUU_LDAP_HOSTNAME)


def configure_openldap():
    src = '/ldap/templates/slapd.conf'
    dest = '/opt/symas/etc/openldap/slapd.conf'
    accesslog_file = '/ldap/static/accesslog.conf'
    gluu_accesslog_file = '/ldap/static/o_gluu_accesslog.conf'

    with open(src, 'r') as fp:
        slapd_template = fp.read()

    with open(accesslog_file, 'r') as fp:
        access_log_text = fp.read()

    with open(gluu_accesslog_file, 'r') as fp:
        gluu_accesslog_text = fp.read()

    ctx_data = {
        'openldapSchemaFolder': '/opt/gluu/schema/openldap',
        'openldapTLSCACert': '',
        'openldapTLSCert': '',
        'openldapTLSKey': '',
        'encoded_ldap_pw': consul.kv.get('encoded_ldap_pw'),
        'openldap_accesslog_conf': commentOutText(access_log_text),
        'openldap_gluu_accesslog': commentOutText(gluu_accesslog_text),
    }

    with open(dest, 'w') as fp:
        fp.write(fomatWithDict(slapd_template, ctx_data))


def render_ldif():
    ctx_data = {
        # o_site.ldif
        # has no variables

        # appliance.ldif
        'ldap_use_ssl': consul.kv.get('ldap_use_ssl'),
        # oxpassport-config.ldif
        'inumAppliance': consul.kv.get('inumAppliance'),
        # TODO: fix how to get ldap_hostname
        'ldap_hostname': consul.kv.get('ldap_hostname'),
        # TODO: currently using std ldaps port 1636 as ldap port.
        # after basic testing we need to do it right, and remove this hack.
        # to do this properly we need to update all templates.
        'ldaps_port': consul.kv.get('ldap_port'),
        'ldap_binddn': consul.kv.get('ldap_binddn'),
        'encoded_ox_ldap_pw': consul.kv.get('encoded_ox_ldap_pw'),
        'jetty_base': consul.kv.get('jetty_base'),

        # asimba.ldif
        # attributes.ldif
        # groups.ldif
        # oxidp.ldif
        # scopes.ldif
        'inumOrg': r"{}".format(consul.kv.get('inumOrg')),  # raw string

        # base.ldif
        'orgName': consul.kv.get('orgName'),

        # clients.ldif
        'oxauth_client_id': consul.kv.get('oxauth_client_id'),
        'oxauthClient_encoded_pw': consul.kv.get('oxauthClient_encoded_pw'),
        'hostname': consul.kv.get('hostname'),

        # configuration.ldif
        'oxauth_config_base64': consul.kv.get('oxauth_config_base64'),
        'oxauth_static_conf_base64': consul.kv.get('oxauth_static_conf_base64'),
        'oxauth_openid_key_base64': consul.kv.get('oxauth_openid_key_base64'),
        'oxauth_error_base64': consul.kv.get('oxauth_error_base64'),
        'oxtrust_config_base64': consul.kv.get('oxtrust_config_base64'),
        'oxtrust_cache_refresh_base64': consul.kv.get('oxtrust_cache_refresh_base64'),
        'oxtrust_import_person_base64': consul.kv.get('oxtrust_import_person_base64'),
        'oxidp_config_base64': consul.kv.get('oxidp_config_base64'),
        'oxcas_config_base64': consul.kv.get('oxcas_config_base64'),
        'oxasimba_config_base64': consul.kv.get('oxasimba_config_base64'),

        # passport.ldif
        'passport_rs_client_id': consul.kv.get('passport_rs_client_id'),
        'passport_rs_client_base64_jwks': consul.kv.get('passport_rs_client_base64_jwks'),
        'passport_rp_client_id': consul.kv.get('passport_rp_client_id'),
        'passport_rp_client_base64_jwks': consul.kv.get('passport_rp_client_base64_jwks'),

        # people.ldif
        "encoded_ldap_pw": consul.kv.get('encoded_ldap_pw'),

        # scim.ldif
        'scim_rs_client_id': consul.kv.get('scim_rs_client_id'),
        'scim_rs_client_base64_jwks': consul.kv.get('scim_rs_client_base64_jwks'),
        'scim_rp_client_id': consul.kv.get('scim_rp_client_id'),
        'scim_rp_client_base64_jwks': consul.kv.get('scim_rp_client_base64_jwks'),

        # scripts.ldif
        # already coverd at this point
    }

    ldif_template_base = '/ldap/templates/ldif'
    pattern = '/*.ldif'
    for file_path in glob.glob(ldif_template_base+pattern):
        with open(file_path, 'r') as fp:
            template = fp.read()
        # render
        rendered_content = template % ctx_data
        # write to tmpdir
        with open(os.path.join(TMPDIR, os.path.basename(file_path)), 'w') as fp:
            fp.write(rendered_content)


def import_ldif():
    ldif_import_order = [
                        'base.ldif',
                        'appliance.ldif',
                        'attributes.ldif',
                        'scopes.ldif',
                        'clients.ldif',
                        'people.ldif',
                        'groups.ldif',
                        'o_site.ldif',
                        'scripts.ldif',
                        'configuration.ldif',
                        'scim.ldif',
                        'asimba.ldif',
                        'passport.ldif',
                        'oxpassport-config.ldif',
                        'oxidp.ldif'
                    ]

    slapadd_cmd = '/opt/symas/bin/slapadd'
    config = '/opt/symas/etc/openldap/slapd.conf'

    for ldif_file in ldif_import_order:
        ldif_file_path = os.path.join(TMPDIR, ldif_file)
        if 'site.ldif' in ldif_file_path:
            runcmd([slapadd_cmd, '-b', 'o=site', '-f', config, '-l', ldif_file_path])
        else:
            runcmd([slapadd_cmd, '-b', 'o=gluu', '-f', config, '-l', ldif_file_path])


def cleanup():
    shutil.rmtree(TMPDIR)


# TODO: Remove oxtrust related code from openldap
# oxtrust start
def reindent(text, num_spaces=1):
    text = [(num_spaces * " ") + line.lstrip() for line in text.splitlines()]
    text = "\n".join(text)
    return text


def generate_base64_contents(text, num_spaces=1):
    text = text.encode("base64").strip()
    if num_spaces > 0:
        text = reindent(text, num_spaces)
    return text


def oxtrust_config():
    # keeping redundent data in context of ldif ctx_data dict for now.
    # so that we can easily remove it from here
    ctx = {
        'inumOrg': r"{}".format(consul.kv.get('inumOrg')),  # raw string
        'admin_email': consul.kv.get('admin_email'),
        'inumAppliance': consul.kv.get('inumAppliance'),
        'hostname': consul.kv.get('hostname'),
        'shibJksFn': consul.kv.get('shibJksFn'),
        'shibJksPass': consul.kv.get('shibJksPass'),
        'jetty_base': consul.kv.get('jetty_base'),
        'oxTrustConfigGeneration': consul.kv.get('oxTrustConfigGeneration'),
        'encoded_shib_jks_pw': consul.kv.get('encoded_shib_jks_pw'),
        'oxauth_client_id': consul.kv.get('oxauth_client_id'),
        'oxauthClient_encoded_pw': consul.kv.get('oxauthClient_encoded_pw'),
        'scim_rs_client_id': consul.kv.get('scim_rs_client_id'),
        'scim_rs_client_jks_fn': consul.kv.get('scim_rs_client_jks_fn'),
        'scim_rs_client_jks_pass_encoded': consul.kv.get('scim_rs_client_jks_pass_encoded'),
        'passport_rs_client_id': consul.kv.get('passport_rs_client_id'),
        'passport_rs_client_jks_fn': consul.kv.get('passport_rs_client_jks_fn'),
        'passport_rs_client_jks_pass_encoded': consul.kv.get('passport_rs_client_jks_pass_encoded'),
        'shibboleth_version': consul.kv.get('shibboleth_version'),
        'idp3Folder': consul.kv.get('idp3Folder'),
        'orgName': consul.kv.get('orgName'),
        'ldap_site_binddn': consul.kv.get('ldap_site_binddn'),
        'encoded_ox_ldap_pw': consul.kv.get('encoded_ox_ldap_pw'),
        'ldap_hostname': consul.kv.get('ldap_hostname'),
        'ldaps_port': consul.kv.get('ldaps_port'),
    }

    oxtrust_template_base = '/ldap/templates/oxtrust'

    key_and_jsonfile_map = {
        'oxtrust_cache_refresh_base64': 'oxtrust-cache-refresh.json',
        'oxtrust_config_base64': 'oxtrust-config.json',
        'oxtrust_import_person_base64': 'oxtrust-import-person.json'
    }

    for key, json_file in key_and_jsonfile_map.iteritems():
        json_file_path = os.path.join(oxtrust_template_base, json_file)
        with open(json_file_path, 'r') as fp:
            consul.kv.set(key, generate_base64_contents(fp.read() % ctx))
# oxtrust end


def run():
    set_kv()
    configure_openldap()
    oxtrust_config()
    render_ldif()
    import_ldif()
    cleanup()


if __name__ == '__main__':
    run()


# related setup functions,
# start_services
# install_ldap_server
# install_openldap (done in dockerfile)
# configure_openldap
# import_ldif_openldap
