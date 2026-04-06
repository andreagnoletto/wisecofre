from celery import shared_task


@shared_task
def sync_ldap_users():
    """Synchronize users and groups from configured LDAP directories.

    Steps:
    1. Fetch all enabled LDAPConfiguration entries.
    2. For each configuration, bind to the LDAP server.
    3. Search for users using user_filter under base_dn.
    4. Search for groups using group_filter under base_dn.
    5. Create/update local User records and group memberships.
    6. Deactivate users that no longer exist in LDAP.
    """
