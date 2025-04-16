"""
Gestisce le connessioni ai database tramite SSH tunnel e connessioni dirette.
"""
import io
import paramiko  # type: ignore[import]
from sshtunnel import SSHTunnelForwarder  # type: ignore[import]
from sqlalchemy import create_engine  # type: ignore[import]
from sqlalchemy.sql import text   # type: ignore
from backend.utils.logging import get_logger


logger = get_logger(__name__)


class ConnectionManager:
    """Gestisce le connessioni ai database."""

    @staticmethod
    def create_ssh_tunnel(ssh_host, ssh_user, ssh_key, db_host, db_port, db_type="postgresql"):
        """
        Crea un tunnel SSH per connettersi al database remoto e ritorna l'oggetto server.
        Supporta sia PostgreSQL che SQL Server.

        Args:
            ssh_host (str): Hostname o IP del server SSH
            ssh_user (str): Username SSH
            ssh_key (str): Chiave privata SSH come stringa
            db_host (str): Hostname o IP del server database
            db_port (str): Porta del server database
            db_type (str): Tipo di database ("postgresql" o "sqlserver")

        Returns:
            tuple: (SSHTunnelForwarder, int) - Oggetto tunnel SSH e porta locale

        Raises:
            Exception: In caso di errore nella creazione del tunnel
        """
        try:
            logger.info(f"🔌 Creazione del tunnel SSH verso {ssh_host} per connettersi a {db_host}:{db_port} ({db_type})")

            # Creazione della chiave privata corretta
            pkey = paramiko.RSAKey(file_obj=io.StringIO(ssh_key))

            # Determina la porta locale in base al tipo di database per evitare conflitti
            local_port = 5433 if db_type == "postgresql" else 5434

            server = SSHTunnelForwarder(
                (ssh_host, 22),
                ssh_username=ssh_user,
                ssh_pkey=pkey,
                remote_bind_address=(db_host, int(db_port)),
                local_bind_address=('127.0.0.1', local_port),
                set_keepalive=10.0,
            )
            server.start()
            logger.info(f"✅ Tunnel SSH creato con successo per {db_type} sulla porta locale {local_port}!")
            return server, local_port
        except Exception as e:
            logger.error(f"❌ Errore nel tunnel SSH: {e}")
            raise

    @staticmethod
    def create_db_engine(config, local_port=None):
        """
        Crea un engine SQLAlchemy per connettersi al database.

        Args:
            config (dict): Configurazione del database
            local_port (int, optional): Porta locale (se si usa tunnel SSH)

        Returns:
            sqlalchemy.engine.Engine: Engine per la connessione al database

        Raises:
            Exception: In caso di errore nella creazione dell'engine
        """
        try:
            db_type = config.get("db_type", "postgresql")
            host = "127.0.0.1" if local_port else config.get("host", "localhost")
            port = local_port or config.get("port", "5432")
            user = config.get("user", "")
            password = config.get("password", "")
            database = config.get("database", "")

            # Costruisci la stringa di connessione in base al tipo di database
            if db_type == "sqlserver":
                db_url = f"mssql+pymssql://{user}:{password}@{host}:{port}/{database}"
            else:  # postgresql (default)
                db_url = f"postgresql://{user}:{password}@{host}:{port}/{database}"

            logger.info(f"🔗 Creazione connessione a {db_type} su {host}:{port}")

            # Crea l'engine con timeout di connessione
            engine = create_engine(
                db_url,
                pool_pre_ping=True,
            )

            return engine
        except Exception as e:
            logger.error(f"❌ Errore nella creazione dell'engine: {e}")
            raise

    @staticmethod
    def test_connection(ssh_config, db_config):
        """
        Testa la connessione SSH e al database.

        Args:
            ssh_config (dict): Configurazione SSH
            db_config (dict): Configurazione database

        Returns:
            dict: Risultato del test con stato e messaggi di errore
        """
        ssh_tunnel = None
        result = {
            "ssh_success": False,
            "db_success": False,
            "ssh_error": "",
            "db_error": ""
        }

        try:
            # Test SSH
            if ssh_config.get("use_ssh", False):
                try:
                    ssh_tunnel, local_port = ConnectionManager.create_ssh_tunnel(
                        ssh_config.get("ssh_host", ""),
                        ssh_config.get("ssh_user", ""),
                        ssh_config.get("ssh_key", ""),
                        db_config.get("host", ""),
                        db_config.get("port", ""),
                        db_config.get("db_type", "postgresql")
                    )
                    result["ssh_success"] = True
                except Exception as e:
                    result["ssh_error"] = str(e)
                    return result
            else:
                # Se non usiamo SSH, marchiamo comunque come successo
                result["ssh_success"] = True
                local_port = None

            # Test database
            try:
                engine = ConnectionManager.create_db_engine(db_config, local_port)

                # Tentiamo una semplice query per verificare che funzioni
                with engine.connect() as connection:
                    connection.execute(text("SELECT 1"))

                result["db_success"] = True
            except Exception as e:
                result["db_error"] = str(e)

            return result
        finally:
            # Chiudiamo il tunnel SSH se è stato aperto
            if ssh_tunnel and ssh_tunnel.is_active:
                ssh_tunnel.stop()
                logger.info("🔌 Tunnel SSH chiuso")
