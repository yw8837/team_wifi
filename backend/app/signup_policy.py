"""Shared signup-age checks; self-declaration is not identity verification."""
from . import config

PUBLIC_MINIMUM_AGE = 14
POLICY_VERSION = '20261105'


def signup_age_confirmed(body):
    # Old installed clients still attest to 18+. Accept that stronger declaration
    # only when the new field is absent; explicit false/null must never fall back.
    if config.PUBLIC_RELEASE and 'age_confirmed' in body.model_fields_set:
        return body.age_confirmed is True
    return body.adult_confirmed is True


def signup_consent_action(body, *, social=False):
    if not config.PUBLIC_RELEASE:
        return ('beta-terms-20261101-privacy-20261101-adult-accepted' if config.BETA
                else 'terms-v1-and-privacy-v1-accepted')
    current = 'age_confirmed' in body.model_fields_set
    version = POLICY_VERSION if current else '20261102'
    declaration = 'age14-self-confirmed' if current else 'legacy-age18-self-confirmed'
    channel = 'social' if social else 'public'
    return f'{channel}-terms-{version}-privacy-{version}-{declaration}'
