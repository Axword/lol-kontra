"""Validate the separate application role before a production release starts."""
import os
import psycopg2
from psycopg2 import sql


_ROLE_ISOLATION_QUERY = """
SELECT candidate.oid, EXISTS (
    SELECT 1 FROM pg_roles privileged
    WHERE pg_has_role(candidate.oid, privileged.oid, 'MEMBER')
      AND (
        privileged.rolsuper OR privileged.rolcreatedb OR privileged.rolcreaterole
        OR privileged.rolreplication OR privileged.rolbypassrls
        OR privileged.rolname IN ('pg_read_server_files', 'pg_write_server_files', 'pg_execute_server_program')
        OR privileged.oid IN (
            SELECT datdba FROM pg_database WHERE datname = current_database()
            UNION SELECT nspowner FROM pg_namespace
                WHERE nspname !~ '^pg_' AND nspname <> 'information_schema'
            UNION SELECT relation.relowner FROM pg_class relation
                JOIN pg_namespace namespace ON namespace.oid = relation.relnamespace
                WHERE namespace.nspname !~ '^pg_' AND namespace.nspname <> 'information_schema'
                  AND relation.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
        )
      )
) FROM pg_roles candidate WHERE candidate.rolname = %s
"""


def check_runtime_database(owner_connection):
    user, password = os.getenv('POSTGRES_APP_USER'), os.getenv('POSTGRES_APP_PASSWORD')
    if user is None and password is None:
        return
    if not user or not password:
        raise ValueError('Both runtime database credentials must be configured')
    if len(password) < 16 or password.lower() in ('lolroster', 'postgres', 'password', 'change-me', 'changeme'):
        raise ValueError('Runtime database credentials require a non-default secret of at least 16 characters')
    if user == owner_connection.settings_dict['USER']:
        raise ValueError('Runtime database role must differ from the migration owner')
    try:
        with owner_connection.cursor() as cursor:
            # MEMBER includes indirect and NOINHERIT membership: SET ROLE can
            # otherwise restore owner powers despite the ordinary ACL checks.
            cursor.execute(_ROLE_ISOLATION_QUERY, [user])
            role = cursor.fetchone()
            if not role or role[1]:
                raise ValueError('Runtime database role must be isolated from administrative and object-owner roles')
            # Schema history belongs to the deploy owner, even though ordinary
            # tables inherit CRUD grants from that owner when they are created.
            cursor.execute(sql.SQL('REVOKE INSERT, UPDATE, DELETE ON public.django_migrations FROM {}').format(sql.Identifier(user)))
        params = dict(owner_connection.get_connection_params())
        params.update(user=user, password=password, connect_timeout=10)
        with psycopg2.connect(**params) as runtime:
            with runtime.cursor() as cursor:
                cursor.execute('SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication FROM pg_roles WHERE rolname=current_user')
                flags = cursor.fetchone()
                if not flags or any(flags):
                    raise ValueError('Runtime database role must not have administrative privileges')
                cursor.execute("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
                if cursor.fetchone()[0]:
                    raise ValueError('Runtime database role must not create schema objects')
                cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")
                tables = [row[0] for row in cursor.fetchall()]
                for table in tables:
                    privileges = ('SELECT',) if table == 'django_migrations' else ('SELECT', 'INSERT', 'UPDATE', 'DELETE')
                    for privilege in privileges:
                        cursor.execute('SELECT has_table_privilege(current_user, %s, %s)', [f'public.{table}', privilege])
                        if not cursor.fetchone()[0]:
                            raise ValueError(f'Runtime database role lacks {privilege} on {table}')
                cursor.execute("SELECT bool_and(has_sequence_privilege(current_user, c.oid, 'USAGE')) "
                               "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='S'")
                if cursor.fetchone()[0] is False:
                    raise ValueError('Runtime database role lacks sequence access')
                cursor.execute("SELECT has_table_privilege(current_user, 'public.django_migrations', 'UPDATE')")
                if cursor.fetchone()[0]:
                    raise ValueError('Runtime database role must not change migration history')
    except psycopg2.Error:
        # Do not include connection strings, raw server messages or secrets.
        raise ValueError('Runtime database connection or grants are invalid') from None
