import pyodbc
from semantic_kernel.functions.kernel_function_decorator import kernel_function


class SQLPlugin:
    """
    update_file_type(table, record_id, new_type) → OK
    """

    def __init__(self):
        pass
    # helpers internos
    def _execute(self, query: str, params: tuple):
        with pyodbc.connect(self.conn_str, autocommit=True) as cnx:
            with cnx.cursor() as cur:
                cur.execute(query, params)

    # función expuesta
    @kernel_function(
        name="update_file_type",
        description="Actualiza la columna file_type para una fila existente",
    )
    def update_file_type(self, table: str, record_id: int, new_type: str) -> str:
        q = f"UPDATE {table} SET file_type = ? WHERE id = ?"
        self._execute(q, (new_type, record_id))
        return "database updated"
