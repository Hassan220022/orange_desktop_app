from alarm_app.bdt.discovery import is_raw_bdt_workbook_filename


def test_raw_bdt_workbook_filename_accepts_site_bdt_export():
    assert is_raw_bdt_workbook_filename("01_S_SG-MUHAFZA-NB1_0704UP_0704UP_BDT.XLSX")


def test_raw_bdt_workbook_filename_rejects_human_acceptance_register():
    assert not is_raw_bdt_workbook_filename("BDT Acceptance Sheet_2026.xlsx")


def test_raw_bdt_workbook_filename_rejects_external_bdt_summary():
    assert not is_raw_bdt_workbook_filename("Huawei_BDT Summary_Last Update.xlsx")


def test_raw_bdt_workbook_filename_rejects_temp_and_non_excel_files():
    assert not is_raw_bdt_workbook_filename("~$0704UP_BDT.xlsx")
    assert not is_raw_bdt_workbook_filename("._0704UP_BDT.xlsx")
    assert not is_raw_bdt_workbook_filename("0704UP_BDT.csv")
