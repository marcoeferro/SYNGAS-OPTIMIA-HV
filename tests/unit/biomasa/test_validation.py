"""Tests de invariantes."""

from __future__ import annotations

import pandas as pd
import pytest

from optimia_hv.biomasa.transformers.reconciliation import DEFAULT_KEY, PROD_COL
from optimia_hv.biomasa.transformers.validation import validar_reconciliacion


def test_validacion_pasa_con_dataset_correcto(
    df_reconciliation_sample: pd.DataFrame,
) -> None:
    from optimia_hv.biomasa.transformers.reconciliation import reconciliar_por_mayor_produccion
    df_final, _ = reconciliar_por_mayor_produccion(
        df_reconciliation_sample, DEFAULT_KEY, PROD_COL
    )
    validar_reconciliacion(df_final, df_reconciliation_sample, DEFAULT_KEY)


def test_validacion_falla_con_duplicados(
    df_reconciliation_sample: pd.DataFrame,
) -> None:
    with pytest.raises(AssertionError, match="duplicados"):
        validar_reconciliacion(
            df_reconciliation_sample, df_reconciliation_sample, DEFAULT_KEY
        )