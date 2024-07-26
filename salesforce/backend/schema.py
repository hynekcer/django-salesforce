"""
Minimal code to support ignored makemigrations  (like django.db.backends.*.schema)

without interaction to SF (without migrate)
"""
from typing import Any, Dict, List, Type, Union
import logging
import re
import time

import requests
from django.db import NotSupportedError
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.backends.ddl_references import Statement
from django.db.models import Field, Model, PROTECT
from salesforce.dbapi.exceptions import OperationalError, SalesforceError

log = logging.getLogger(__name__)

# souce: https://gist.github.com/wadewegner/9139536
METADATA_ENVELOPE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:apex="http://soap.sforce.com/2006/08/apex"
                  xmlns:cmd="http://soap.sforce.com/2006/04/metadata"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <soapenv:Header>
    <cmd:SessionHeader>
      <cmd:sessionId>{session_id}</cmd:sessionId>
    </cmd:SessionHeader>
  </soapenv:Header>
  <soapenv:Body>
{body}
  </soapenv:Body>
</soapenv:Envelope>
"""

CREATE_OBJECT_BODY = """
    <create xmlns="http://soap.sforce.com/2006/04/metadata">
      <metadata xsi:type="CustomObject">
{body}
      </metadata>
    </create>
"""

DELETE_METADATA_BODY = """
    <cmd:deleteMetadata>
      <cmd:type>{metadata_type}</cmd:type>
      <cmd:fullNames>{custom_object_name}</cmd:fullNames>
    </cmd:deleteMetadata>
"""

T_PY2XML = Union[str, int, float, Dict[str, Union['T_PY2XML', List['T_PY2XML']]]]  # type: ignore[misc] # recursive


def to_xml(data: T_PY2XML, indent: int = 0) -> str:
    """Format a simple XML body for SOAP API from data very similar to REST API

    Examples are in: salesforce.tests.test_unit.ToXml
    """
    INDENT = 2  # indent step
    if isinstance(data, str):
        return data.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    elif isinstance(data, (int, float)):
        return str(data)
    elif isinstance(data, dict):
        out = []  # type: List[str]
        for tag, val in data.items():
            assert re.match(r'[A-Za-z][0-9A-Za-z_:]*$', tag)
            if not isinstance(val, list):
                val = [val]
            for item in val:
                v_str = to_xml(item, indent + 1)
                wrap_start = '\n' if v_str.endswith('>') else ''
                wrap_end = '\n' + indent * INDENT * ' ' if v_str.endswith('>') else ''
                out.append(indent * INDENT * ' ' + '<{tag}>{wrap_start}{v_str}{wrap_end}</{tag}>'
                           .format(tag=tag, v_str=v_str, wrap_start=wrap_start, wrap_end=wrap_end))
        return '\n'.join(out)
    else:
        raise NotImplementedError("Not implemented conversion from type {} to xml".format(type(data)))


class DatabaseSchemaEditor(BaseDatabaseSchemaEditor):
    # pylint:disable=abstract-method  # undefined: prepare_default, quote_value

    DISPLAY_FORMAT = 'A-{0}'

    deferred_sql: List[str]

    def __init__(self, connection, collect_sql=False, atomic=True):
        self.conn = connection.connection
        self.connection = connection.connection
        self.collect_sql = collect_sql
        # if self.collect_sql:
        #    self.collected_sql = []
        log.debug('DatabaseSchemaEditor __init__')
        self.cur = self.conn.cursor()
        self.request = self.conn.handle_api_exceptions
        self._permission_set_id = None  # Optional[str]
        self.permission_set_id  # require the permission set
        super().__init__(connection, collect_sql=collect_sql, atomic=atomic)

    # State-managing methods

    def __enter__(self) -> 'DatabaseSchemaEditor':
        log.debug('DatabaseSchemaEditor __enter__')
        self.deferred_sql = []
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        # called at the end of every migrations
        log.debug('DatabaseSchemaEditor __exit__')
        if exc_type is None:
            for sql in self.deferred_sql:
                self.execute(sql)

    def create_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        db_table = model._meta.db_table
        sf_managed_model = getattr(model._meta.auto_field, 'sf_managed_model', False)
        if sf_managed_model or model._meta.db_table == 'django_migrations__c':
            body = CREATE_OBJECT_BODY.format(body=to_xml(self.make_model_metadata(model), indent=4))
            response_text = self.metadata_command(action='create', body=body, is_async=True)
            # <?xml version="1.0" encoding="UTF-8"?>
            # <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
            #                   xmlns="http://soap.sforce.com/2006/04/metadata">
            #   <soapenv:Body>
            #     <createResponse>
            #       <result>
            #         <done>false</done>
            #         <id>04sM0000001l43CIAQ</id>
            #         <state>InProgress</state>
            #       </result>
            #     </createResponse>
            #   </soapenv:Body>
            # </soapenv:Envelope>
            match = re.match(r'.*<id>([0-9A-Za-z]{18})</id>', response_text)
            assert match
            async_result_id = match.group(1)
            entity_id = self.wait_for_entity(db_table, async_result_id)

            object_permissions_data = dict(
                # selection by `db_table` was not reliable if the same object is in the trash
                SobjectType=entity_id,
                ParentId=self.permission_set_id,
                # PermissionsViewAllRecords=True,
                # PermissionsModifyAllRecords=True,
                PermissionsRead=True,
                PermissionsEdit=True,
                PermissionsCreate=True,
                PermissionsDelete=True,
            )
            ret = self.request('POST', 'sobjects/ObjectPermissions', json=object_permissions_data)
            assert ret.status_code == 201

        for field in model._meta.fields:
            sf_managed_field = (getattr(field, 'sf_managed', False) or db_table == 'django_migrations__c'
                                and field.column.lower() != 'id')
            if sf_managed_field:
                if db_table == 'django_migrations__c':
                    field.column += '__c'
                self.add_field(model, field)

    def delete_model(self, model: Type[Model]) -> None:
        if model._meta.db_table == 'django_migrations':
            model._meta.db_table += '__c'
        sf_managed_model = getattr(model._meta.auto_field, 'sf_managed_model', False)
        if sf_managed_model or model._meta.db_table == 'django_migrations__c':
            log.debug("delete_model %s", model)
            self.delete_metadata('CustomObject', model._meta.db_table)
        else:
            for field in model._meta.fields:
                sf_managed_field = getattr(field, 'sf_managed', False)
                if sf_managed_field:
                    self.remove_field(model, field)

    def add_field(self, model: Type[Model], field: Field) -> None:
        # the assert is more general to work alos for more special operations e.g. for some rename
        assert field.model._meta.db_table == model._meta.db_table
        sf_managed = getattr(field, 'sf_managed', False) or model._meta.db_table == 'django_migrations__c'
        if sf_managed:
            full_name = model._meta.db_table + '.' + field.column
            metadata = self.make_field_metadata(field)
            data = {'Metadata': metadata, 'FullName': full_name}

            log.debug("add_field %s %s", model, full_name)
            ret = self.request('POST', 'tooling/sobjects/CustomField', json=data)
            assert ret.status_code == 201
            # ret.json() == {'id': '00NM0000002KYDHMA4', 'success': True, 'errors': [], 'warnings': [], 'infos': []}

            # FeldPermissions.objects.create(sobject_type='Donation__c', field='Donation__c.Amount__c',
            #                                permissions_edit=True, permissions_read=True, parent=ps)
            if not metadata.get('required'):
                field_permissions_data = {
                    'SobjectType': model._meta.db_table,
                    'Field': full_name,
                    'ParentId': self.permission_set_id,
                    'PermissionsEdit': True,
                    'PermissionsRead': True,
                }
                ret = self.request('POST', 'sobjects/FieldPermissions', json=field_permissions_data)
                assert ret.status_code == 201

    def remove_field(self, model: Type[Model], field: Field) -> None:
        sf_managed_field = getattr(field, 'sf_managed', False)
        if sf_managed_field:
            full_name = model._meta.db_table + '.' + field.column
            log.debug("remove_field %s %s", model, full_name)
            self.delete_metadata('CustomField', full_name)
            # developer_name = self.developer_name(old_field.column)
            # self.cur.execute("select Id from CustomField where TableEnumOrId = %s and DeveloperName = %s",
            #                  [model._meta.db_table, developer_name],
            #                   tooling_api=True)
            # pk, = self.cur.fetchone()
            # # SalesforceError: INSUFFICIENT_ACCESS_ON_CROSS_REFERENCE_ENTITY
            # ret = self.request('DELETE', 'tooling/sobjects/CustomField/{}'.format(pk))
            # assert ret and ret.status_code == 204

    def alter_field(self, model: Type[Model], old_field: Field, new_field: Field, strict: bool = False
                    ) -> None:
        """This can rename a field or change the type or the parameters"""
        sf_managed_field = getattr(old_field, 'sf_managed', False) or getattr(new_field, 'sf_managed', False)
        if sf_managed_field:
            developer_name = self.developer_name(old_field.column)
            self.cur.execute("select Id from CustomField where TableEnumOrId = %s and DeveloperName = %s",
                             [model._meta.db_table, developer_name],
                             tooling_api=True)
            field_id, = self.cur.fetchone()
            full_name = model._meta.db_table + '.' + new_field.column
            metadata = self.make_field_metadata(new_field)
            data = {'Metadata': metadata, 'FullName': full_name}
            log.debug("alter_field %s %s to %s", model, old_field, full_name)
            ret = self.request('PATCH', 'tooling/sobjects/CustomField/{}'.format(field_id), json=data)
            assert ret.status_code == 204

    def execute(self, sql: Union[Statement, str], params: Any = ()) -> None:
        assert isinstance(sql, str)
        raise NotSupportedError("Migration SchemaEditor: %r, %r" % (sql, params))

    # -- private methods

    @staticmethod
    def developer_name(api_name: str) -> str:
        return api_name.rsplit('__', 1)[0]

    @property
    def permission_set_id(self) -> str:
        if not self._permission_set_id:
            self.cur.execute("select Id from PermissionSet where Name = %s", ['Django_Salesforce'])
            rows = self.cur.fetchall()
            if rows:
                self._permission_set_id, = rows[0]
            else:
                raise OperationalError("Can not migrate because the Permission Set 'Django_Salesforce' doesn't exist")
        return self._permission_set_id

    def metadata_command(self, action: str, body: str, is_async: bool = False) -> str:
        # TODO move to the driver
        data = METADATA_ENVELOPE.format(
            session_id=self.conn.sf_session.auth.get_auth()['access_token'],
            body=body,
        )
        self.cur.execute('select id from Organization')
        org_id, = self.cur.fetchone()
        url = '{instance_url}/services/Soap/m/{api_version}/{org_id}'.format(
            instance_url=self.conn.sf_auth.instance_url,
            api_version=self.conn.api_ver,
            org_id=org_id,
        )
        headers = {'SOAPAction': action, 'Content-Type': 'text/xml; charset=utf-8'}
        # the header {'Expect': '100-continue'} is useful if sending much data and want
        # to check headers by the server before uploading the body
        ret = requests.request('POST', url, data=data, headers=headers)
        async_progress = is_async and '<state>InProgress</state>' in ret.text
        if ret.status_code != 200 or 'success>true</success>' not in ret.text and not async_progress:
            raise SalesforceError("Failed metadata {action}, code: {status_code}, response {text!r}".format(
                action=action, status_code=ret.status_code, text=ret.text
            ))
        return ret.text

    def make_field_metadata(self, field: Field) -> Dict[str, Any]:
        # pylint:disable=too-many-branches
        db_type = field.db_type(self.connection)
        metadata = {
            'label': field.verbose_name,
            'type': db_type,
            'inlineHelpText': field.help_text,
            'required': not field.null and not field.blank,  # not 'required' if empty string is possible
            'unique': field.unique,  # type: ignore[attr-defined]
        }
        # if
        #    metadata['defaultValue'] =

        # by db_type
        if db_type == 'Checkbox':
            del metadata['required']
            metadata['defaultValue'] = field.default
        elif db_type in ('Date', 'DateTime'):
            pass
        elif db_type == 'Number':
            # TODO try with a default value and without
            metadata['precision'] = field.max_digits  # type: ignore[attr-defined]
            metadata['scale'] = field.decimal_places  # type: ignore[attr-defined]
        elif db_type in ('Text', 'Email', 'URL'):
            metadata['length'] = field.max_length
        elif db_type == 'Lookup':
            metadata.pop('defaultValue', None)
            # TODO "Related List Label" "Child Relationship Name"
            metadata['referenceTo'] = field.related_model._meta.db_table  # type: ignore[union-attr]
            metadata['relationshipName'] = field.remote_field.get_accessor_name()  # type: ignore[attr-defined]
            # metadata['relationshipLabel'] = metadata['relationshipName']  # not important
            metadata['deleteConstraint'] = (
                'Restrict' if field.remote_field.on_delete is PROTECT  # type: ignore[attr-defined]
                else 'SetNull')
        elif db_type == 'Picklist':
            pass  # TODO copy choices from sf_syncdb
        else:
            raise NotImplementedError
        return metadata

    def make_model_metadata(self, model: Type[Model]) -> Dict[str, Any]:
        for field in model._meta.fields:
            if field.column == 'Name':
                name_field = field
                break
        else:
            name_field = None
        name_writable = getattr(name_field, 'sf_read_only', 3) == 0
        name_label = getattr(name_field, 'name', 'Name')
        name_metadata = {
            'label': name_label,
            'type': 'Text' if name_writable else 'AutoNumber',
        }
        if not name_writable:
            name_metadata['displayFormat'] = self.DISPLAY_FORMAT
        metadata = {
            'fullName': model._meta.db_table,
            'label': model._meta.verbose_name,
            'pluralLabel': str(model._meta.verbose_name_plural),
            'deploymentStatus': 'Deployed',
            'sharingModel': 'ReadWrite',
            'nameField': name_metadata,
        }
        return metadata

    def delete_metadata(self, metadata_type: str, full_name: str) -> None:
        # can be modified to a list of custom fields field names
        body = DELETE_METADATA_BODY.format(metadata_type=metadata_type, custom_object_name=full_name)
        self.metadata_command(action='delete', body=body)
    def wait_for_entity(self, db_table: str, deploy_result_id: str) -> str:
        t0 = time.time()
        dt = 0.05
        # wait for table creation
        cur2 = self.conn.cursor(dict)
        while True:
            if time.time() - t0 > 30:
                raise TimeoutError()
            time.sleep(dt)
            dt *= 1.2
            # soql = "select DeveloperName from CustomObject where DeveloperName = %s limit 2"
            soql = ("select DeveloperName, Label, QualifiedApiName, DeploymentStatus, RunningUserEntityAccessId "
                    "from EntityDefinition where QualifiedApiName = %s limit 2")
            cur2.execute(soql, [db_table], tooling_api=True)
            rows = cur2.fetchall()
            if rows:
                assert len(rows) == 1
                entity_id = rows[0]['RunningUserEntityAccessId'].split('.')[0]
                wait_elapsed = round(time.time() - t0, 3)
                log.debug('create_model %s; time:%f, pk:%s, rows:%s', db_table, wait_elapsed, deploy_result_id, rows)
                break
        return entity_id

    # def prepare_default(self, value):    # TODO
    #     return self.quote_value(value)
