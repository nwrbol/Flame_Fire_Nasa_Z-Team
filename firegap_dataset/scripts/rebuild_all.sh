#!/bin/bash
# Rebuild the merged dataset. Usage: bash rebuild_all.sh   (run from /home/claude)
U=/mnt/user-data/uploads
python3 -I scripts/psi_pipeline.py out \
 saffire1:psi_extract/i_Investigation.txt:$U/920079ff-PSI-98_Experimental_table_SAFFIRE-1.csv \
 saffire2:psi_extract2/i_Investigation.txt:$U/d2939636-PSI-99_Experimental_table_SAFFIRE-2.csv \
 saffire3:psi_extract3/i_Investigation.txt:$U/e27ab742-PSI-100_Experimental_table_SAFFIRE-3.csv \
 flex:psi_extract4/i_Investigation.txt:$U/7801b65e-PSI-69_Experimental_table_FLEX.csv \
 flex2env:psi_extract5/i_Investigation.txt:$U/32ff4b87-PSI-68_Experimental_table_Flex2.csv \
 bass2:psi_extract7/i_Investigation.txt:$U/60e614aa-PSI-25_Experimental_table_BASS-II.csv \
 bass:psi_extract8/i_Investigation.txt:$U/3a82452a-BASS_test_matrix.xlsx \
 "cfig:psi_extract9/i_Investigation.txt:$U/f94b55bc-PSI-159_Experimental_table_CFI-G_Normal_Flames.csv|$U/9cfb961b-PSI-159_Experimental_table_CFI-G_Inverse_Flames.csv" \
 "flamedesign:psi_extract10/i_Investigation.txt:$U/c3e6e814-PSI-10_Experimental_table_Flame_Design_Normal_Flame.csv|$U/a2ca0475-PSI-10_Experimental_table_Flame_Design_Inverse_Flame.csv" \
 cld:psi_extract11/i_Investigation.txt:$U/8b495383-PSI-21_Experimental_table_CLD_Flame.csv \
 efield:psi_extract12/i_Investigation.txt:data/efield_table1_from_30day_report.csv \
 sflame:psi_extract13/i_Investigation.txt:$U/f5b6729b-PSI-23_Experimental_table_ACME_s-Flame.csv \
 "bre:psi_extract14/i_Investigation.txt:data/bre_days_corrected.csv|data/bre_per_flame_from_dissertation.csv"
