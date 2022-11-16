from unittest import mock

import sqlglot
from sqlglot.dataframe.sql import functions as F
from sqlglot.dataframe.sql import types
from sqlglot.dataframe.sql.session import SparkSession
from sqlglot.schema import MappingSchema
from tests.dataframe.unit.dataframe_sql_validator import DataFrameSQLValidator


class TestDataframeSession(DataFrameSQLValidator):
    def test_cdf_one_row(self):
        df = self.spark.createDataFrame([[1, 2]], ["cola", "colb"])
        expected = "SELECT `a2`.`cola` AS `cola`, `a2`.`colb` AS `colb` FROM VALUES (1, 2) AS `a2`(`cola`, `colb`)"
        self.compare_sql(df, expected)

    def test_cdf_multiple_rows(self):
        df = self.spark.createDataFrame([[1, 2], [3, 4], [None, 6]], ["cola", "colb"])
        expected = "SELECT `a2`.`cola` AS `cola`, `a2`.`colb` AS `colb` FROM VALUES (1, 2), (3, 4), (NULL, 6) AS `a2`(`cola`, `colb`)"
        self.compare_sql(df, expected)

    def test_cdf_no_schema(self):
        df = self.spark.createDataFrame([[1, 2], [3, 4], [None, 6]])
        expected = "SELECT `a2`.`_1` AS `_1`, `a2`.`_2` AS `_2` FROM VALUES (1, 2), (3, 4), (NULL, 6) AS `a2`(`_1`, `_2`)"
        self.compare_sql(df, expected)

    def test_cdf_row_mixed_primitives(self):
        df = self.spark.createDataFrame([[1, 10.1, "test", False, None]])
        expected = "SELECT `a2`.`_1` AS `_1`, `a2`.`_2` AS `_2`, `a2`.`_3` AS `_3`, `a2`.`_4` AS `_4`, `a2`.`_5` AS `_5` FROM VALUES (1, 10.1, 'test', FALSE, NULL) AS `a2`(`_1`, `_2`, `_3`, `_4`, `_5`)"
        self.compare_sql(df, expected)

    def test_cdf_dict_rows(self):
        df = self.spark.createDataFrame([{"cola": 1, "colb": "test"}, {"cola": 2, "colb": "test2"}])
        expected = "SELECT `a2`.`cola` AS `cola`, `a2`.`colb` AS `colb` FROM VALUES (1, 'test'), (2, 'test2') AS `a2`(`cola`, `colb`)"
        self.compare_sql(df, expected)

    def test_cdf_str_schema(self):
        df = self.spark.createDataFrame([[1, "test"]], "cola: INT, colb: STRING")
        expected = "SELECT CAST(`a2`.`cola` AS INT) AS `cola`, CAST(`a2`.`colb` AS STRING) AS `colb` FROM VALUES (1, 'test') AS `a2`(`cola`, `colb`)"
        self.compare_sql(df, expected)

    def test_typed_schema_basic(self):
        schema = types.StructType(
            [
                types.StructField("cola", types.IntegerType()),
                types.StructField("colb", types.StringType()),
            ]
        )
        df = self.spark.createDataFrame([[1, "test"]], schema)
        expected = "SELECT CAST(`a2`.`cola` AS INT) AS `cola`, CAST(`a2`.`colb` AS STRING) AS `colb` FROM VALUES (1, 'test') AS `a2`(`cola`, `colb`)"
        self.compare_sql(df, expected)

    def test_typed_schema_nested(self):
        schema = types.StructType(
            [
                types.StructField(
                    "cola",
                    types.StructType(
                        [
                            types.StructField("sub_cola", types.IntegerType()),
                            types.StructField("sub_colb", types.StringType()),
                        ]
                    ),
                )
            ]
        )
        df = self.spark.createDataFrame([[{"sub_cola": 1, "sub_colb": "test"}]], schema)
        expected = "SELECT CAST(`a2`.`cola` AS STRUCT<`sub_cola`: INT, `sub_colb`: STRING>) AS `cola` FROM VALUES (STRUCT(1 AS `sub_cola`, 'test' AS `sub_colb`)) AS `a2`(`cola`)"

        self.compare_sql(df, expected)

    @mock.patch("sqlglot.schema", MappingSchema())
    def test_sql_select_only(self):
        # TODO: Do exact matches once CTE names are deterministic
        query = "SELECT cola, colb FROM table"
        sqlglot.schema.add_table("table", {"cola": "string", "colb": "string"})
        df = self.spark.sql(query)
        self.assertIn(
            "SELECT `table`.`cola` AS `cola`, `table`.`colb` AS `colb` FROM `table` AS `table`",
            df.sql(pretty=False),
        )

    @mock.patch("sqlglot.schema", MappingSchema())
    def test_sql_with_aggs(self):
        # TODO: Do exact matches once CTE names are deterministic
        query = "SELECT cola, colb FROM table"
        sqlglot.schema.add_table("table", {"cola": "string", "colb": "string"})
        df = self.spark.sql(query).groupBy(F.col("cola")).agg(F.sum("colb"))
        result = df.sql(pretty=False, optimize=False)[0]
        self.assertIn("SELECT cola, colb FROM table", result)
        self.assertIn("SUM(colb)", result)
        self.assertIn("GROUP BY cola", result)

    @mock.patch("sqlglot.schema", MappingSchema())
    def test_sql_create(self):
        query = "CREATE TABLE new_table AS WITH t1 AS (SELECT cola, colb FROM table) SELECT cola, colb, FROM t1"
        sqlglot.schema.add_table("table", {"cola": "string", "colb": "string"})
        df = self.spark.sql(query)
        expected = "CREATE TABLE new_table AS SELECT `table`.`cola` AS `cola`, `table`.`colb` AS `colb` FROM `table` AS `table`"
        self.compare_sql(df, expected)

    @mock.patch("sqlglot.schema", MappingSchema())
    def test_sql_insert(self):
        query = "WITH t1 AS (SELECT cola, colb FROM table) INSERT INTO new_table SELECT cola, colb FROM t1"
        sqlglot.schema.add_table("table", {"cola": "string", "colb": "string"})
        df = self.spark.sql(query)
        expected = "INSERT INTO new_table SELECT `table`.`cola` AS `cola`, `table`.`colb` AS `colb` FROM `table` AS `table`"
        self.compare_sql(df, expected)

    def test_session_create_builder_patterns(self):
        spark = SparkSession()
        self.assertEqual(spark.builder.appName("abc").getOrCreate(), spark)