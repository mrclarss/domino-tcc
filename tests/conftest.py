import os
import tempfile

import pytest

os.environ.setdefault("LIGA_INSTANCE", tempfile.mkdtemp())


@pytest.fixture()
def app():
    from liga import create_app
    from liga.security import reset_rate_limits

    reset_rate_limits()
    application = create_app()
    application.config.update(TESTING=True)
    return application


@pytest.fixture()
def client(app):
    return app.test_client()
