from marshmallow import ValidationError, Schema as MaSchema, missing
from marshmallow import fields as ma_fields, validates_schema
import bson

from .i18n import gettext as _


__all__ = (
    'schema_validator_check_unknown_fields',
    'schema_from_umongo_get_attribute',
    'SchemaFromUmongo',

    'ObjectId',
    'Reference',
    'GenericReference'
)


# Bonus: schema helpers !


def schema_validator_check_unknown_fields(self, data, original_data):
    """
    Schema validator, raise ValidationError for unknown fields in a
    marshmallow schema.

    example::

        class MySchema(marshsmallow.Schema):
            # method's name is not important
            __check_unknown_fields = validates_schema(pass_original=True)(
                schema_validator_check_unknown_fields)

            # Define the rest of your schema
            ...

    """
    loadable_fields = [k for k, v in self.fields.items() if not v.dump_only]
    unknown_fields = {key for key in original_data if key not in loadable_fields}
    if unknown_fields:
        raise ValidationError([_('Unknown field name {field}.').format(field=field)
                               for field in unknown_fields])


def schema_from_umongo_get_attribute(self, attr, obj, default):
    """
    Overwrite default `Schema.get_attribute` method by this one to access
        umongo missing fields instead of returning `None`.

    example::

        class MySchema(marshsmallow.Schema):
            get_attribute = schema_from_umongo_get_attribute

            # Define the rest of your schema
            ...

    """
    ret = MaSchema.get_attribute(self, attr, obj, default)
    if ret is None and ret is not default:
        raw_ret = obj._data.get(attr)
        return default if raw_ret is missing else raw_ret
    else:
        return ret


class SchemaFromUmongo(MaSchema):
    """
    Custom :class:`marshmallow.Schema` subclass providing unknown fields
    checking and custom get_attribute for umongo documents.

    .. note: It is not mandatory to use this schema with umongo document.
        This is just a helper providing usefull behaviors.
    """

    __check_unknown_fields = validates_schema(pass_original=True)(
                schema_validator_check_unknown_fields)
    get_attribute = schema_from_umongo_get_attribute


# Bonus: new fields !


class ObjectId(ma_fields.Field):
    """
    Marshmallow field for :class:`bson.ObjectId`
    """

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        return str(value)

    def _deserialize(self, value, attr, data):
        if value is None:
            return None
        try:
            return bson.ObjectId(value)
        except bson.errors.InvalidId:
            raise ValidationError(_('Invalid ObjectId.'))


class Reference(ObjectId):
    """
    Mashmallow field for :class:`umongo.fields.ReferenceField`
    """

    def __init__(self, *args, mongo_world=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.mongo_world = mongo_world

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        if self.mongo_world:
            # In mongo world, value is a regular ObjectId
            return str(value)
        else:
            # In OO world, value is a :class:`umongo.data_object.Reference`
            return str(value.pk)


class GenericReference(ma_fields.Field):
    """
    Mashmallow field for :class:`umongo.fields.GenericReferenceField`
    """

    def __init__(self, *args, mongo_world=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.mongo_world = mongo_world

    def _serialize(self, value, attr, obj):
        if value is None:
            return None
        if self.mongo_world:
            # In mongo world, value a dict of cls and id
            return {'id': str(value['_id']), 'cls': value['_cls']}
        else:
            # In OO world, value is a :class:`umongo.data_object.Reference`
            return {'id': str(value.pk), 'cls': value.document_cls.__name__}

    def _deserialize(self, value, attr, data):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise ValidationError(_("Invalid value for generic reference field."))
        if value.keys() != {'cls', 'id'}:
            raise ValidationError(_("Generic reference must have `id` and `cls` fields."))
        try:
            _id = bson.ObjectId(value['id'])
        except ValueError:
            raise ValidationError(_("Invalid `id` field."))
        if self.mongo_world:
            return {'_cls': value['cls'], '_id': _id}
        else:
            return {'cls': value['cls'], 'id': _id}