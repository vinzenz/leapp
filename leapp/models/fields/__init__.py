import copy
import datetime
import six


def missing():
    pass


class ModelViolationError(Exception):
    """
    ModelViolationError is raised if the data in the instances is not matching its definition.
    """
    def __init__(self, message):
        super(ModelViolationError, self).__init__(message)


class ModelMisuseError(Exception):
    """
    ModelMisuseError is raised if the Model definition is not valid.
    """
    def __init__(self, message):
        super(ModelMisuseError, self).__init__(message)


class Field(object):
    """
    Field is the base of all supported fields.
    """
    @property
    def help(self):
        """
        :return: Documentation help string defining what the field is about.
        """
        return self._help or 'No documentation provided for this field `{}`'.format(type(self).__name__)

    def __init__(self, default=missing, required=False, allow_null=False, help=None):
        """
        :param default: Default value to be used if the field is not set
        :param required: Marks the field as mandatory
        :type required: bool
        :param allow_null: Decides whether or not the field is allowed to be None
        :type allow_null: bool
        :param help: Documentation string for generating model documentation
        :type help: str
        """
        self._help = help
        self._default = default
        self._required = required
        self._allow_null = allow_null

        if type(self) == Field:
            raise ModelMisuseError("Do not use this type directly.")

    def _validate_model_value(self, value, name):
        """
        Validates the value in the Model representation

        :param value: Value to be checked
        :param name: Name of the field (used for a better error reporting only)
        :return: None
        """
        if value is None and not self._allow_null:
            raise ModelViolationError('The {name} attribute is None, but this is not allowed'.format(name=name))
        if value is missing and self._required:
            raise ModelViolationError('The {name} attribute is not set, but it is required'.format(name=name))

    def _validate_builtin_value(self, value, name):
        """
        Validates the value in the builtin representation

        :param value: Value to be checked
        :param name: Name of the field (used for a better error reporting only)
        :return: None
        """
        if value is None and not self._allow_null:
            raise ModelViolationError('The {name} field is null, but this is not allowed'.format(name=name))

    def _convert_to_model(self, value, name):
        """
        Performs the conversion from a builtin type to the model representation

        :param value: Value to convert
        :param name: Name of the field (used for a better error reporting only)
        :return: Converted value in the model format
        """
        self._validate_builtin_value(value=value, name=name)
        return value

    def _convert_from_model(self, value, name):
        """
        Performs the conversion from a model type to the builtin representation

        :param value: Value to convert
        :param name: Name of the field (used for a better error reporting only)
        :return: Converted value in the builtin format
        """
        self._validate_model_value(value=value, name=name)
        return value

    def from_initialization(self, source, name, target):
        """
        Assigns the value to the target model passed through during the model initialization

        :param source: Dictionary to extract the value from (usually kwargs)
        :type source: dict
        :param name: Name of the field (used for a better error reporting only)
        :type name: str
        :param target: Target model instance
        :type target: Instance of a Model derived class
        :return: None
        """
        source_value = source.get(name, self._default)
        self._validate_model_value(value=source_value, name=name)
        setattr(target, name, source_value)

    def to_model(self, source, name, target):
        """
        Converts the value with the given name to the model representation and assigns the attribute

        :param source: Dictionary to extract the value from
        :type source: dict
        :param name: Name of the field (used for a better error reporting only)
        :type name: str
        :param target: Target model instance
        :type target: Instance of a Model derived class
        :return: None
        """
        source_value = source.get(name, self._default)
        target_value = source_value
        if not (source_value is missing and not self._required):
            target_value = self._convert_to_model(value=source_value, name=name)
        setattr(target, name, target_value)

    def to_builtin(self, source, name, target):
        """
        Converts the value with the given name to the builtin representation and assigns the field

        :param source: Source model to get the value from
        :type source: Instance of a Model derived class
        :param name: Name of the field (used for a better error reporting only)
        :type name: str
        :param target: Dictionary to set the value to
        :type target: dict
        :return: None
        """
        target_value = self._convert_from_model(getattr(source, name, None), name=name)
        if target_value is not missing:
            target[name] = target_value


class BuiltinField(Field):
    """
    Base class for all builtin types to act as pass-through with an additional validation
    """

    @property
    def _model_type(self):
        """
        :return: Returns the type to be used as a model type representation
        """
        raise NotImplementedError("_model_type needs to be overridden")

    @property
    def _builtin_type(self):
        """
        :return: Returns the type to be used as a builtin type representation (e.g. string)
        """
        return self._model_type

    def _validate_model_value(self, value, name):
        super(BuiltinField, self)._validate_model_value(value, name)
        self._validate(value=value, name=name, expected_type=self._model_type)

    def _validate_builtin_value(self, value, name):
        super(BuiltinField, self)._validate_builtin_value(value, name)
        self._validate(value=value, name=name, expected_type=self._builtin_type)

    def _validate(self, value, name, expected_type):
        if not isinstance(expected_type, tuple):
            expected_type = (expected_type,)
        if not self._required and value is missing:
            return
        if value is not None and not any(isinstance(value, t) for t in expected_type):
            names = ', '.join(['{}'.format(t.__name__) for t in expected_type])
            raise ModelViolationError("Fields {} is of type: {} expected: {}".format(name, type(value).__name__,
                                                                                     names))


class Boolean(BuiltinField):
    """
    Boolean field
    """
    @property
    def _model_type(self):
        return bool


class Float(BuiltinField):
    """
    Float field
    """
    @property
    def _model_type(self):
        return float


class Integer(BuiltinField):
    """
    Integer field (int, long in python 2, int in python 3)
    """
    @property
    def _model_type(self):
        return six.integer_types


class Number(BuiltinField):
    """
    Combined Integer and Float field
    """
    @property
    def _model_type(self):
        return six.integer_types + (float,)


class String(BuiltinField):
    """
    String field
    """
    @property
    def _model_type(self):
        return six.string_types + (six.binary_type,)


class DateTime(BuiltinField):
    """
    DateTime field to handle datetime objects which are converted to the ISO format and parsed back from there
    """
    @property
    def _model_type(self):
        return datetime.datetime

    @property
    def _builtin_type(self):
        return six.string_types

    def _convert_to_model(self, value, name):
        self._validate_builtin_value(value=value, name=name)

        if value is None:
            return value

        # We want Z to be appended but it needs support from our side here:
        value = value.rstrip('Z')

        # If there are fractions, use them
        fractions = ''
        if '.' in value:
            fractions = '.%f'

        # Try to parse with timezone specification, else retry without
        try:
            return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S{fractions}%Z'.format(fractions=fractions))
        except ValueError:
            try:
                return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S{fractions}'.format(fractions=fractions))
            except ValueError:
                raise ModelViolationError(
                    "The {name} field contains an invalid datetime value: '{value}'".format(name=name, value=value))

    def _convert_from_model(self, value, name):
        self._validate_model_value(value=value, name=name)

        if value in (None, missing):
            return value

        if not value.utcoffset():
            return value.isoformat() + 'Z'


class EnumMixin(Field):
    """
    EnumMixin adds the ability to use the field as an Enum type of the field
    """
    def __init__(self, choices, **kwargs):
        """
        :param choices: List of values that are allowed for this field
        :type choices: List or tuple of allowed values
        """
        super(EnumMixin, self).__init__(**kwargs)
        if not isinstance(choices, (tuple, list)):
            raise ModelMisuseError("Choices needs to be a list or a tuple")
        self._choices = choices

    def _validate_model_value(self, value, name):
        super(EnumMixin, self)._validate_model_value(value, name)
        self._validate_choices(value, name)

    def _validate_builtin_value(self, value, name):
        super(EnumMixin, self)._validate_builtin_value(value, name)
        self._validate_choices(value, name)

    def _validate_choices(self, value, name):
        if value not in (None, missing) and value not in self._choices:
            values = ", ".join(map(str, self._choices))
            raise ModelViolationError("The {name} field value must be one of '{values}'".format(name=name,
                                                                                                values=values))


class StringEnum(EnumMixin, String):
    """
    Field that represents an enumeration of Strings
    """
    pass


class IntegerEnum(EnumMixin, Integer):
    """
    Field that represents an enumeration of Integers
    """
    pass


class FloatEnum(EnumMixin, Float):
    """
    Field that represents an enumeration of Floats
    """
    pass


class NumberEnum(EnumMixin, Number):
    """
    Field that represents an enumeration of Numbers
    """
    pass


class List(Field):
    """
        List represents lists of `elem_field` values
    """
    def __init__(self, elem_field, minimum=None, maximum=None, **kwargs):
        """
        :param elem_field:
        :type elem: Instance of :py:class:`Field`
        :param minimum: Minimal number of elements
        :type minimum: int or None
        :param maximum: Maximum number of elements
        :type maximum: int or None
        :param default: Default value to use if the field is not set
        :type default: A list of elements with the value type as specified in `elem_field`
        :param required: Marks the field as mandatory
        :type required: bool
        :param allow_null: Decides whether or not the field is allowed to be None
        :type allow_null: bool
        :param help: Documentation string for generating model documentation
        :type help: str
        """
        super(List, self).__init__(**kwargs)
        # We do a copy of the data in default, to avoid some unwanted side effects
        if self._default not in (missing, None):
            self._default = copy.copy(self._default)
        if not isinstance(elem_field, Field):
            raise ModelMisuseError("elem_field must be an instance of a type derived from Field")
        self._elem_type = elem_field
        self._minimum = minimum or 0
        self._maximum = maximum

    def _validate_count(self, value, name):
        message = 'Element count error for field {name} expected between {minimum} and {maximum} elements got {count}'
        count = len(value)
        if not (self._minimum <= count <= (self._maximum or count)):
            raise ModelViolationError(
                message.format(name=name, minimum=self._minimum, maximum=self._maximum or count, count=count))

    def _validate_model_value(self, value, name):
        super(List, self)._validate_model_value(value, name)
        if isinstance(value, (list, tuple)):
            self._validate_count(value, name)
            for idx, entry in enumerate(value):
                self._elem_type._validate_model_value(entry, name='{}[{}]'.format(name, idx))
        elif value and value is not missing:
            raise ModelViolationError('Expected list but got {} for the {} field'.format(type(value).__name__, name))

    def _validate_builtin_value(self, value, name):
        super(List, self)._validate_builtin_value(value, name)
        if isinstance(value, (list, tuple)):
            self._validate_count(value, name)
            for idx, entry in enumerate(value):
                self._elem_type._validate_builtin_value(entry, name='{}[{}]'.format(name, idx))
        elif value is not None:
            raise ModelViolationError('Expected list but got {} for the {} field'.format(type(value).__name__, name))

    def _convert_to_model(self, value, name):
        self._validate_builtin_value(value=value, name=name)
        if value is None:
            return value
        converter = self._elem_type._convert_to_model
        return list(converter(entry, name='{}[{}]'.format(name, idx)) for idx, entry in enumerate(value))

    def _convert_from_model(self, value, name):
        self._validate_model_value(value=value, name=name)
        if value in (None, missing):
            return value
        converter = self._elem_type._convert_from_model
        return list(converter(entry, name='{}[{}]'.format(name, idx)) for idx, entry in enumerate(value))


class Model(Field):
    """
    Model is used to use other Models as fields
    """
    def __init__(self, model_type, **kwargs):
        """
        :param model_type: A :py:class:`leapp.model.Model` derived class
        :type model_type: :py:class:`leapp.model.Model` derived class
        :param default: Default value to use if the field is not set
        :type default: An instance of the type specified in `model_type` or None
        :param required: Marks the field as mandatory
        :type required: bool
        :param allow_null: Decides whether or not the field is allowed to be None
        :type allow_null: bool
        :param help: Documentation string for generating the model documentation
        :type help: str
        """
        super(Model, self).__init__(**kwargs)
        from leapp.models import Model as ModelType
        if not isinstance(model_type, type) or not issubclass(model_type, ModelType):
            raise ModelMisuseError("{} must be a type derived from Field".format(model_type))
        self._model_type = model_type

    def _validate_model_value(self, value, name):
        super(Model, self)._validate_model_value(value, name)
        if value and value is not missing and not isinstance(value, self._model_type):
            raise ModelViolationError('Expected an instance of {} for the {} attribute but got {}'.format(
                self._model_type.__name__, name, type(value)))

    def _validate_builtin_value(self, value, name):
        super(Model, self)._validate_model_value(value, name)
        if value and not isinstance(value, dict):
            raise ModelViolationError('Expected a value for the {} field and got {}'.format(name, type(value).__name__))

    def _convert_to_model(self, value, name):
        self._validate_builtin_value(value, name)
        if value is None:
            return value
        return self._model_type(init_method='to_model', **value)

    def _convert_from_model(self, value, name):
        self._validate_model_value(value, name)
        if value in (None, missing):
            return value
        return value.dump()


class Nested(Model):
    def __init__(self, *args, **kwargs):
        raise ModelMisuseError('Please use leapp.models.fields.Model instead of leapp.models.fields.Nested')
