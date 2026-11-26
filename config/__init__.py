"""Initialisation du paquet config : active PyMySQL comme adaptateur MySQLdb si mysqlclient n'est pas présent."""
try:
    import MySQLdb  # noqa: F401
except ImportError:
    import pymysql

    pymysql.version_info = (2, 2, 8, "final", 0)
    pymysql.install_as_MySQLdb()
