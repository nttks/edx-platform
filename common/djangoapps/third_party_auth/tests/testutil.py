"""
Utilities for writing third_party_auth tests.

Used by Django and non-Django tests; must not have Django deps.
"""

from contextlib import contextmanager
from django.conf import settings
from django.contrib.auth.models import User
from provider.oauth2.models import Client as OAuth2Client
from provider import constants
import django.test
from mako.template import Template
import mock
import os.path

from third_party_auth.models import (
    OAuth2ProviderConfig,
    SAMLProviderConfig,
    SAMLConfiguration,
    LTIProviderConfig,
    cache as config_cache,
    ProviderApiPermissions,
)


AUTH_FEATURES_KEY = 'ENABLE_THIRD_PARTY_AUTH'
AUTH_FEATURE_ENABLED = AUTH_FEATURES_KEY in settings.FEATURES


def patch_mako_templates():
    """ Patch mako so the django test client can access template context """
    orig_render = Template.render_unicode

    def wrapped_render(*args, **kwargs):
        """ Render the template and send the context info to any listeners that want it """
        django.test.signals.template_rendered.send(sender=None, template=None, context=kwargs)
        return orig_render(*args, **kwargs)

    return mock.patch.multiple(Template, render_unicode=wrapped_render, render=wrapped_render)


class FakeDjangoSettings(object):
    """A fake for Django settings."""

    def __init__(self, mappings):
        """Initializes the fake from mappings dict."""
        for key, value in mappings.iteritems():
            setattr(self, key, value)


class ThirdPartyAuthTestMixin(object):
    """ Helper methods useful for testing third party auth functionality """

    def tearDown(self):
        config_cache.clear()
        super(ThirdPartyAuthTestMixin, self).tearDown()

    def enable_saml(self, **kwargs):
        """ Enable SAML support (via SAMLConfiguration, not for any particular provider) """
        kwargs.setdefault('enabled', True)
        # obj = SAMLConfiguration.objects.create()
        obj = SAMLConfiguration(
            enabled=1,
            entity_id='https://idp.testshib.org/idp/shibboleth',
            private_key='MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDnDtun9bP9/630hIRfin6nYAbjds8ZmNWIzcJwZbh73IxrH0OE0zImni2itPhi69OSsd5y82KA2ypcu5MnrgNdhHeMphd7CLQetUCERMfnq2fOdjAqGzKYW901seRJv9c2ZEFOlyhCXaeZqF0nTagZro7rOuTX6RQTWxSYEPQqO5GN5bIKgc1twzsi1dYwhmJaxmbsRhSpph9d7o7JSc+iIahUL+y4uB70vBCJKj9VMhxEsSdr4DIUeOmVZCzbboHO027vqWw9JmbKt117dYtVP1wkH+J8bi+X5LrexlBmuitaqNyeYpa7r8mjH848axi5rPhpz4u9YEdAKim8kNM9AgMBAAECggEAPx9gAtKtCYcADvzk7PT5BODHAP1ENsn6DBWqOOqRK8Vk1x8DYxYPbV1pOjoWYW/rrPfKvbyf/HPjbtIPsZdoc/PsdRAq+gG2s2zw4zGnKzM4eL7xCY/EkrsGA9VFeKBgOwvIi5/f78GGOAQ27rXYZqu5f6nnOtUCFwea6LA5BBAc+TRcxXNoiv8VsGoij1bKg//0aoVOQbOk+XACLFdxlEIkse7AijOCdn3FDZahHy5CPZvpkIbugMfcuNepk5rtAj4IcPa716zXQ4LKeEbqxXptFoPXSZSZNUurghthBFk1nCQdbYy4lsW0b0uskc7157uWif9JSpD99pwhzH2cAQKBgQD/NXNF+bGs6Wu97VoszOs8vgIp3CDfTGkolyWC7sqdXZ92btZuWd9MDF6KXYQnDwBj86j9wUiF3nj/Zpvf3FExV2rRNFU6spDk4dP8k0RUvppbbsUAL2j10s6JEk5gbCicGCicO6T3ixldjy/WYEhx+tK7KMZGWIgd+QmuppdOMQKBgQDnxj19T/PYPyR2WlGGQD2qYHLnH1WVWYzwpCtA+02U7m+JOtzGiRzRZFvB8oRBJFgiTHuXh5Urh1pRHym5gP6mTD2urO2E1qRknxQi+rQHgx/RkTH27XN0pwwd7VBQhqlwTG2Vd2oH60r+ps9P+XuI6LJ0/tY1Ao11WfiNuN8WzQKBgDsyyNR4gRBc7NMXlY1C02Y5pQLUvwNNFC+IL/lZLsKmDvFH8JGUY0merOdnndn5jtugj5idFxeGbYbA5HNfBa5uWqbAfuyosxeEksnJ11XZCLEg1q2eUbiD98iv6GJRdHIQ4IqtAy0wpOeg6TXPC770saEcajGzI4/gTrCmj/5hAoGAHj6YN4n/X/CdaXRPvx0S7vC3DcHhASQ2aBCENG6WqSCUHWw48w9hW1GlR6HF8Fo1xgQE/LkMlimLd5qBb1uN31WDlw+pzvPTb+3ySr48T96kgExaIMbLkiVaR214VYm9ApJ2mlKC25Wwq5pI4z7DCBKVdv7qJPC4VN/wt02wjuECgYAybcZ9uN9z5wZw1K7Yq5+waH3iGUmHVn6G4Yr6RNMpHWfGa/M45ObJBfT2EysFj7a28ilfB2G4wTxuYvTOW/dmL6JAo4XdFb5CgvZzrGcmFZONwfY7nI3FWc1ha+PBlrmzXcVEuYhmofLoyoGZbA50xEe0I0HQz+Rw7mpr/O9/NA==',
            public_key='MIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDnDtun9bP9/630hIRfin6nYAbjds8ZmNWIzcJwZbh73IxrH0OE0zImni2itPhi69OSsd5y82KA2ypcu5MnrgNdhHeMphd7CLQetUCERMfnq2fOdjAqGzKYW901seRJv9c2ZEFOlyhCXaeZqF0nTagZro7rOuTX6RQTWxSYEPQqO5GN5bIKgc1twzsi1dYwhmJaxmbsRhSpph9d7o7JSc+iIahUL+y4uB70vBCJKj9VMhxEsSdr4DIUeOmVZCzbboHO027vqWw9JmbKt117dYtVP1wkH+J8bi+X5LrexlBmuitaqNyeYpa7r8mjH848axi5rPhpz4u9YEdAKim8kNM9AgMBAAECggEAPx9gAtKtCYcADvzk7PT5BODHAP1ENsn6DBWqOOqRK8Vk1x8DYxYPbV1pOjoWYW/rrPfKvbyf/HPjbtIPsZdoc/PsdRAq+gG2s2zw4zGnKzM4eL7xCY/EkrsGA9VFeKBgOwvIi5/f78GGOAQ27rXYZqu5f6nnOtUCFwea6LA5BBAc+TRcxXNoiv8VsGoij1bKg//0aoVOQbOk+XACLFdxlEIkse7AijOCdn3FDZahHy5CPZvpkIbugMfcuNepk5rtAj4IcPa716zXQ4LKeEbqxXptFoPXSZSZNUurghthBFk1nCQdbYy4lsW0b0uskc7157uWif9JSpD99pwhzH2cAQKBgQD/NXNF+bGs6Wu97VoszOs8vgIp3CDfTGkolyWC7sqdXZ92btZuWd9MDF6KXYQnDwBj86j9wUiF3nj/Zpvf3FExV2rRNFU6spDk4dP8k0RUvppbbsUAL2j10s6JEk5gbCicGCicO6T3ixldjy/WYEhx+tK7KMZGWIgd+QmuppdOMQKBgQDnxj19T/PYPyR2WlGGQD2qYHLnH1WVWYzwpCtA+02U7m+JOtzGiRzRZFvB8oRBJFgiTHuXh5Urh1pRHym5gP6mTD2urO2E1qRknxQi+rQHgx/RkTH27XN0pwwd7VBQhqlwTG2Vd2oH60r+ps9P+XuI6LJ0/tY1Ao11WfiNuN8WzQKBgDsyyNR4gRBc7NMXlY1C02Y5pQLUvwNNFC+IL/lZLsKmDvFH8JGUY0merOdnndn5jtugj5idFxeGbYbA5HNfBa5uWqbAfuyosxeEksnJ11XZCLEg1q2eUbiD98iv6GJRdHIQ4IqtAy0wpOeg6TXPC770saEcajGzI4/gTrCmj/5hAoGAHj6YN4n/X/CdaXRPvx0S7vC3DcHhASQ2aBCENG6WqSCUHWw48w9hW1GlR6HF8Fo1xgQE/LkMlimLd5qBb1uN31WDlw+pzvPTb+3ySr48T96kgExaIMbLkiVaR214VYm9ApJ2mlKC25Wwq5pI4z7DCBKVdv7qJPC4VN/wt02wjuECgYAybcZ9uN9z5wZw1K7Yq5+waH3iGUmHVn6G4Yr6RNMpHWfGa/M45ObJBfT2EysFj7a28ilfB2G4wTxuYvTOW/dmL6JAo4XdFb5CgvZzrGcmFZONwfY7nI3FWc1ha+PBlrmzXcVEuYhmofLoyoGZbA50xEe0I0HQz+Rw7mpr/O9/NA==',
            org_info_str={"en-US": {
        "url": "http://www.example.com",
        "displayname": "Example Inc.",
        "name": "example"
            }
        },
        other_config_str=({"SECURITY_CONFIG": {
        "signMetadata": 'false',
        "metadataCacheDuration": 604800
            }
        }))
        obj.save()
        return obj

    @staticmethod
    def configure_oauth_provider(**kwargs):
        """ Update the settings for an OAuth2-based third party auth provider """
        obj = OAuth2ProviderConfig(**kwargs)
        obj.save()
        return obj

    def configure_saml_provider(self, **kwargs):
        """ Update the settings for a SAML-based third party auth provider """
        self.assertTrue(SAMLConfiguration.is_enabled(), "SAML Provider Configuration only works if SAML is enabled.")
        obj = SAMLProviderConfig(**kwargs)
        obj.save()
        return obj

    def is_configure_saml_provider(self, **kwargs):
        """ Update the settings for an SAML-based third party auth provider """
        self.enable_saml(**kwargs)
        obj = SAMLProviderConfig(**kwargs)
        obj.save()
        return obj

    @staticmethod
    def configure_lti_provider(**kwargs):
        """ Update the settings for a LTI Tool Consumer third party auth provider """
        obj = LTIProviderConfig(**kwargs)
        obj.save()
        return obj

    @classmethod
    def configure_google_provider(cls, **kwargs):
        """ Update the settings for the Google third party auth provider/backend """
        kwargs.setdefault("name", "Google")
        kwargs.setdefault("backend_name", "google-oauth2")
        kwargs.setdefault("icon_class", "fa-google-plus")
        kwargs.setdefault("key", "test-fake-key.apps.googleusercontent.com")
        kwargs.setdefault("secret", "opensesame")
        return cls.configure_oauth_provider(**kwargs)

    @classmethod
    def configure_facebook_provider(cls, **kwargs):
        """ Update the settings for the Facebook third party auth provider/backend """
        kwargs.setdefault("name", "Facebook")
        kwargs.setdefault("backend_name", "facebook")
        kwargs.setdefault("icon_class", "fa-facebook")
        kwargs.setdefault("key", "FB_TEST_APP")
        kwargs.setdefault("secret", "opensesame")
        return cls.configure_oauth_provider(**kwargs)


    def configure_azure_ad_provider(self, **kwargs):
        """ Update the settings for the SAML third party auth provider/backend """
        kwargs.setdefault("name", "SAML")
        kwargs.setdefault("backend_name", "tpa-saml")
        kwargs.setdefault("icon_class", "fa-sign-in")
        kwargs.setdefault("idp_slug", "abc")
        kwargs.setdefault("entity_id","https://idp.testshib.org/idp/shibboleth")
        kwargs.setdefault("metadata_source", "https://www.testshib.org/metadata/testshib-providers.xml")
        return self.is_configure_saml_provider(**kwargs)

    def configure_azure_ad_2_provider(self, **kwargs):
        """ Update the settings for the SAML third party auth provider/backend """
        kwargs.setdefault("name", "SAML")
        kwargs.setdefault("backend_name", "tpa-saml")
        kwargs.setdefault("icon_class", "fa-sign-in")
        kwargs.setdefault("idp_slug", "cde")
        kwargs.setdefault("entity_id","https://idp.testshib.org/idp/shibboleth")
        kwargs.setdefault("metadata_source", "https://www.testshib.org/metadata/testshib-providers.xml")
        return self.is_configure_saml_provider(**kwargs)

    @classmethod
    def configure_linkedin_provider(cls, **kwargs):
        """ Update the settings for the LinkedIn third party auth provider/backend """
        kwargs.setdefault("name", "LinkedIn")
        kwargs.setdefault("backend_name", "linkedin-oauth2")
        kwargs.setdefault("icon_class", "fa-linkedin")
        kwargs.setdefault("key", "test")
        kwargs.setdefault("secret", "test")
        return cls.configure_oauth_provider(**kwargs)

    @classmethod
    def configure_twitter_provider(cls, **kwargs):
        """ Update the settings for the Twitter third party auth provider/backend """
        kwargs.setdefault("name", "Twitter")
        kwargs.setdefault("backend_name", "twitter")
        kwargs.setdefault("icon_class", "fa-twitter")
        kwargs.setdefault("key", "test")
        kwargs.setdefault("secret", "test")
        return cls.configure_oauth_provider(**kwargs)

    @classmethod
    def configure_dummy_provider(cls, **kwargs):
        """ Update the settings for the Twitter third party auth provider/backend """
        kwargs.setdefault("name", "Dummy")
        kwargs.setdefault("backend_name", "dummy")
        return cls.configure_oauth_provider(**kwargs)

    @classmethod
    def verify_user_email(cls, email):
        """ Mark the user with the given email as verified """
        user = User.objects.get(email=email)
        user.is_active = True
        user.save()

    @staticmethod
    def configure_oauth_client():
        """ Configure a oauth client for testing """
        return OAuth2Client.objects.create(client_type=constants.CONFIDENTIAL)

    @staticmethod
    def configure_api_permission(client, provider_id):
        """ Configure the client and provider_id pair. This will give the access to a client for that provider. """
        return ProviderApiPermissions.objects.create(client=client, provider_id=provider_id)

    @staticmethod
    def read_data_file(filename):
        """ Read the contents of a file in the data folder """
        with open(os.path.join(os.path.dirname(__file__), 'data', filename)) as f:
            return f.read()


class TestCase(ThirdPartyAuthTestMixin, django.test.TestCase):
    """Base class for auth test cases."""
    def setUp(self):
        super(TestCase, self).setUp()
        # Explicitly set a server name that is compatible with all our providers:
        # (The SAML lib we use doesn't like the default 'testserver' as a domain)
        self.client.defaults['SERVER_NAME'] = 'example.none'
        self.url_prefix = 'http://example.none'


class SAMLTestCase(TestCase):
    """
    Base class for SAML-related third_party_auth tests
    """
    @classmethod
    def _get_public_key(cls, key_name='saml_key'):
        """ Get a public key for use in the test. """
        return cls.read_data_file('{}.pub'.format(key_name))

    @classmethod
    def _get_private_key(cls, key_name='saml_key'):
        """ Get a private key for use in the test. """
        return cls.read_data_file('{}.key'.format(key_name))

    def enable_saml(self, **kwargs):
        """ Enable SAML support (via SAMLConfiguration, not for any particular provider) """
        if 'private_key' not in kwargs:
            kwargs['private_key'] = self._get_private_key()
        if 'public_key' not in kwargs:
            kwargs['public_key'] = self._get_public_key()
        kwargs.setdefault('entity_id', "https://saml.example.none")
        super(SAMLTestCase, self).enable_saml(**kwargs)


@contextmanager
def simulate_running_pipeline(pipeline_target, backend, email=None, fullname=None, username=None):
    """Simulate that a pipeline is currently running.

    You can use this context manager to test packages that rely on third party auth.

    This uses `mock.patch` to override some calls in `third_party_auth.pipeline`,
    so you will need to provide the "target" module *as it is imported*
    in the software under test.  For example, if `foo/bar.py` does this:

    >>> from third_party_auth import pipeline

    then you will need to do something like this:

    >>> with simulate_running_pipeline("foo.bar.pipeline", "google-oauth2"):
    >>>    bar.do_something_with_the_pipeline()

    If, on the other hand, `foo/bar.py` had done this:

    >>> import third_party_auth

    then you would use the target "foo.bar.third_party_auth.pipeline" instead.

    Arguments:

        pipeline_target (string): The path to `third_party_auth.pipeline` as it is imported
            in the software under test.

        backend (string): The name of the backend currently running, for example "google-oauth2".
            Note that this is NOT the same as the name of the *provider*.  See the Python
            social auth documentation for the names of the backends.

    Keyword Arguments:
        email (string): If provided, simulate that the current provider has
            included the user's email address (useful for filling in the registration form).

        fullname (string): If provided, simulate that the current provider has
            included the user's full name (useful for filling in the registration form).

        username (string): If provided, simulate that the pipeline has provided
            this suggested username.  This is something that the `third_party_auth`
            app generates itself and should be available by the time the user
            is authenticating with a third-party provider.

    Returns:
        None

    """
    pipeline_data = {
        "backend": backend,
        "kwargs": {
            "details": {}
        }
    }
    if email is not None:
        pipeline_data["kwargs"]["details"]["email"] = email
    if fullname is not None:
        pipeline_data["kwargs"]["details"]["fullname"] = fullname
    if username is not None:
        pipeline_data["kwargs"]["username"] = username

    pipeline_get = mock.patch("{pipeline}.get".format(pipeline=pipeline_target), spec=True)
    pipeline_running = mock.patch("{pipeline}.running".format(pipeline=pipeline_target), spec=True)

    mock_get = pipeline_get.start()
    mock_running = pipeline_running.start()

    mock_get.return_value = pipeline_data
    mock_running.return_value = True

    try:
        yield

    finally:
        pipeline_get.stop()
        pipeline_running.stop()
