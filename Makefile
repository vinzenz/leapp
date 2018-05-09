CONFDIR=${DESTDIR}/etc/leapp
LIBDIR=${DESTDIR}/var/lib/leapp

install-deps:
	pip install -r requirements.txt

install:
	install -dm 0755 ${CONFDIR}
	install -m 0744 etc/leapp/leapp.conf ${CONFDIR}
	install -m 0744 etc/leapp/logger.conf ${CONFDIR}
	install -dm 0755 ${LIBDIR}
	python -c "import sqlite3; sqlite3.connect('${LIBDIR}/audit.db').executescript(open('res/audit-layout.sql', 'r').read())"

install-container-test:
	echo 'Container install'

install-test:
	pip install -r requirements-tests.txt

container-test:
	echo 'Container Test run'

test:
	py.test --flake8 --cov leapp

.PHONY: install-deps install install-test test
