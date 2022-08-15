class ModelUpdateMixin:
    """Add update() on Django model instance, similar to queryset.update()."""

    def update(self, **updated_fields):
        if not updated_fields:
            return

        for key, value in updated_fields.items():
            setattr(self, key, value)

        self.save(update_fields=updated_fields.keys())
