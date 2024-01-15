class ValidationManager:
    def __init__(self, validators):
        self.validators = validators

    def validate_all(self):
        errors = []
        for validator in self.validators:
            errors.extend(validator.validate().err_messages)
        return errors
