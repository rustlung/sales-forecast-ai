class ForecastingError(Exception):
    """Expected domain error safe to show in the CLI."""


class UnsupportedTargetError(ForecastingError):
    pass


class InsufficientHistoryError(ForecastingError):
    pass


class MissingDatesError(ForecastingError):
    pass


class ValidationImpossibleError(ForecastingError):
    pass


class ProphetTrainingError(ForecastingError):
    pass
