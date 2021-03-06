from branch_predictor_info import BranchPredictorInfo
from btb import BTB
from tournament_pred import TournamentPred
import numpy as np

def print_pct_taken():
	num_taken = 0
	for branch_event in BranchPredictorInfo.grouped_branch_seqs:
		if branch_event["is_taken"]:
			num_taken += 1
	pct_taken = \
	num_taken / len(BranchPredictorInfo.grouped_branch_seqs)
	print(round(pct_taken * 100, 2))

def print_std_pc(): # in bytes
	pc_list = []
	for branch_event in BranchPredictorInfo.grouped_branch_seqs:
		pc_list.append(int(branch_event["instr"]["pc"], 16))
	print(round(np.std(pc_list), 2))

def print_num_branches():
	print(len(BranchPredictorInfo.grouped_branch_seqs))

def simulate_tp(width: int):
	tp = TournamentPred(width = width)
	correct_preds = 0
	for branch_event in BranchPredictorInfo.grouped_branch_seqs:
		pc_sel = int( \
		(int(branch_event["instr"]["pc"], 16) / (2**width)) \
		% (2**width)
		)
		is_taken_pred = \
		tp.get_prediction(pc_sel)
		if is_taken_pred == branch_event["is_taken"]:
			correct_preds += 1
		else:
			tp.update_predictor(
				branch_event["is_taken"],
				pc_sel
			)
	pct_correct = \
	correct_preds / len(BranchPredictorInfo.grouped_branch_seqs)
	# print(f"TABLE_WIDTH: {width}; pct_correct: {pct_correct * 100}")	
	print(round(pct_correct * 100, 2))

def simulate_btb(width: int):
	btb = BTB()
	correct_preds = 0
	total_taken_pred = 0
	tp = TournamentPred(width = width)
	for branch_event in BranchPredictorInfo.grouped_branch_seqs:
		pc_lookup = int(branch_event["instr"]["pc"], 16)
		pc_pred = btb.get_prediction(pc_lookup)
		pc_sel = int( \
		(int(branch_event["instr"]["pc"], 16) / (2**width)) \
		% (2**width)
		)
		is_taken_pred = tp.get_prediction(pc_sel) 
		if is_taken_pred != branch_event["is_taken"]:
			tp.update_predictor(
				branch_event["is_taken"],
				pc_sel
			)
		if is_taken_pred and branch_event["is_taken"]:
			total_taken_pred += 1
			if branch_event["actual_pc"] == pc_pred:
				correct_preds += 1
		if branch_event["is_taken"]:
			btb.update_predictor(
				pc_lookup, 
				pc_targ = branch_event["actual_pc"]
			)
	pct_correct = \
	correct_preds / total_taken_pred
	# print(f"TABLE_WIDTH: {width}; pct_correct: {pct_correct * 100}")	
	print(round(pct_correct * 100, 2))

"""
Analyzes the user-specified RISCV instruction file
"""
if __name__ == "__main__":
	BranchPredictorInfo.init()
	# print(BranchPredictorInfo.get_str())
	print("% taken")
	print_pct_taken()
	print("std pc of branch instrs in bytes")
	print_std_pc()
	print("num branches")
	print_num_branches()
	for width in range(1, 9):
		# print(str(width) + ":")
		# print("% accuracy for tp:")
		# simulate_tp(width)
		# print("% accuracy for BTB w/ tp:")
		simulate_btb(width)
