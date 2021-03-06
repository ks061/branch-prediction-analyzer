"""
Modified fetch_decode.py in the 
pyriscv folder within the RISC-V
Sodor 1-Stage processor lab series

Kartikeya Sharma
Class: CSCI 320
Professor Marchiori
"""

# filename: fetch_decode.py
from alu import ALU, AluFunVal
from branch_cond_gen import BranchCondGen
from branch_targ_gen import BranchTargGen
from control_signals import ControlSignals
from datamem import DataMem
import itertools
from itype import IType
from jump_targ_gen import JumpTargGen
from mux import make_mux 
from pydigital.memory import readmemh, Memory, MemorySegment
from pydigital.register import Register
from pydigital.utils import sextend
from regfile import RegFile
from riscv_isa.isa import Instruction, regNumToName
from riscv_isa.instr_codes import instrTypes
from stype import SType
import sys
from utype import UType

# the PC register
PC = Register()
 
# construct a memory segment for instruction memory
# load the contents from the 32-bit fetch_test hex file (big endian)
if len(sys.argv) >= 2: mem_address = sys.argv[1]
else: mem_address = "riscv_isa/programs/fetch_test.hex"
imem = readmemh(mem_address,
   word_size = 4, byteorder = 'big')
 
def display():
   if instr == None:
       return "PC: xxxxxxxx, IR: xxxxxxxx"
   else:
       return f"PC: {PC.out():08x}, IR: {instr.val:08x}, {instr}"

def _get_debug_str():
   # retrieval of params for debugging
   rs1_index = instr.get_rs1() 
   rs2_index = instr.get_rs2()
   rd_index = instr.get_rd()
   if rs1_index != None: rs1_val = RegFile.get_rs1()
   else: rs1_val = None
   if rs2_index != None: rs2_val = RegFile.get_rs2()
   else: rs2_val = None
   if rd_index != None: rd_val = RegFile.reg_vals[instr.get_rd()]
   else: rd_val = None
   i_imm = instr.get_imm() 
   op = instr.get_opcode()
   func3 = instr.get_funct3()
   func7 = instr.get_funct7()
   alu_fun_index = ControlSignals.get_alufun()
   alu_fun = AluFunVal(alu_fun_index).name
   
   UNKNOWN_REG_VAL = "xxxxxxxx"
   UNKNOWN_REG_INDEX = " [xXX]"
   if i_imm == None: i_imm = 0
   if func3 == None: func3 = 0
   if func7 == None: func7 = 0

   debug_str = " rd: "
   if rd_val == None or rd_index == None: debug_str += UNKNOWN_REG_VAL
   else: debug_str += f"{rd_val:8x}"
   if rd_index == None: debug_str += UNKNOWN_REG_INDEX
   else: debug_str += f" [x{rd_index:2d}]"
   debug_str += " rs1: "
   if rs1_val == None or rs1_index == None: debug_str += UNKNOWN_REG_VAL
   else: debug_str += f"{rs1_val:8x}"
   if rs1_index == None: debug_str += UNKNOWN_REG_INDEX
   else: debug_str += f" [x{rs1_index:2d}]"
   debug_str += " rs2: "
   if rs2_val == None or rs2_index == None: debug_str += UNKNOWN_REG_VAL
   else: debug_str += f"{rs2_val:8x}"
   if rs2_index == None: debug_str += UNKNOWN_REG_INDEX
   else: debug_str += f" [x{rs2_index:2d}]"
   debug_str += " imm: "
   debug_str += f"{i_imm:04x}"
   debug_str += f" op: {op:02x}"
   debug_str += " func3: "
   debug_str += f"{func3}"
   debug_str += " func7: "
   debug_str += f"{func7}"
   debug_str += f" alu_fun: ALU_{alu_fun}"
   return debug_str

def full_display():
   # print one line w/ instruction
   print(f"{t:20d}:", display())
   
   # then display debug line
   print(_get_debug_str())
   print()

   # then display regs
   RegFile.display()

def _handle_ecall():
   if instr._mnemonic.upper() == "ECALL":
       if RegFile.reg_vals[10] == 0:
           print("ECALL(0): HALT")
           return True # if returns True, processor must stop
       if RegFile.reg_vals[10] == 1:
           print("ECALL(" + str(RegFile.reg_vals[10]) + "): " + str(RegFile.reg_vals[11]))
       if RegFile.reg_vals[10] == 10:
           print("ECALL(10): EXIT")
           return True
   return False

# mux setup helper funcs
def _raise_jalr_pc_sel_excep():
    raise Exception("jalr pc selection not implemented.")

def _raise_excep_pc_sel_excep():
    raise Exception("exception pc selection not implemented.")

# mux setup

pc_sel_mux = make_mux(
    lambda: PC.out() + 4,
    lambda: _raise_jalr_pc_sel_excep(),
    BranchTargGen.get_branch,
    JumpTargGen.get_jump,
    lambda: _raise_excep_pc_sel_excep()
)

op1sel_mux = make_mux(RegFile.get_rs1, UType.get_imm)
op2sel_mux = make_mux(RegFile.get_rs2, SType.get_imm, IType.get_imm, PC.out)

WORD_SIZE_BITS = 32
WORD_SIZE_BYTES = 4 # 2 binary places right shift to
                    # go from byte address to  word address

_mem_seg = MemorySegment(
    begin_addr = 0xE0000,
    count = (0xEFFFF - 0xE0000 + 1) >> 2,
    word_size = WORD_SIZE_BYTES
)
_mem = Memory(segment=_mem_seg)
data_mem = DataMem.init(_mem)
 
wb_sel_mux = make_mux(DataMem.get_read_data, # non-implemented input;
                                  # mux index reserved
                      lambda: ALU.alu(op1sel_mux(ControlSignals.get_op1sel()),
                              op2sel_mux(ControlSignals.get_op2sel()), 
                              ControlSignals.get_alufun()),
                      lambda: PC.out()+4,
                      lambda: -1) # not implemented; placeholder      

# init other vars for processor loop
startup = True
instr = None

# generate system clocks until we reach a stopping condition
# this is basically the run function from the last lab
for t in itertools.count():
   # RESET the PC register
   if startup:
       print(f"{t:20d}:", display())
       startup=False 
       RegFile.clock(2, 0xEFFFF, True)
       continue
   else:
       # select PC
       if PC.out() == None:
           PC.reset(imem.begin_addr)       
       else:
           PC.clock(pc_sel_mux(ControlSignals.get_pc_sel()))
       
       # check stopping conditions on NEXT instruction
       if PC.out() > 0x1100:
           print("STOP -- PC is large! Is something wrong?")
           break
       if imem[PC.out()] == 0:
           print("Done -- end of program.")
           break
   
   # access instruction memory
   instr = Instruction(imem[PC.out()], PC.out())
   
   # set control signals
   ControlSignals.set_instr_name(instr.get_mnemonic().lower())

   # process imm combinational blocks
   BranchTargGen.set_branch(
       PC.out(),
       (instr.get_val() >> 7) & 0x1f,
       (instr.get_val() >> 25) & 0x7f
   )
   JumpTargGen.set_jump(
       PC.out(),
       (instr.get_val() >> 12) & 0xfffff
   ) 
   IType.set_imm(instr.get_val() >> 20)
   SType.set_imm(
   ((instr.get_val() >> 25) << 5) +
   ((instr.get_val() >> 7) & 0x1f)
   )
   UType.set_imm(instr.get_val() >> 12)

   # update instr imm from imm combo block
   # handling imm's for current instr type   
   instr.update_imm()
 
   # regfile reading (combinational block)
   rs1_index = instr.get_rs1() 
   rs2_index = instr.get_rs2()
   rd_index = instr.get_rd()
   RegFile.read(rs1_index, rs2_index)

   BranchCondGen.set_branch_conds(
       RegFile.get_rs1(),
       RegFile.get_rs2()
   )

   # if previous instuction was a branch 
   # instruction, then see if branch was taken
   if ((instr._get_instr_name_equivalence(["BEQ"]) and
      BranchCondGen.get_br_eq()) or
      (instr._get_instr_name_equivalence(["BNE"]) and
      not BranchCondGen.get_br_eq()) or
      (instr._get_instr_name_equivalence(["BLT"]) and
      BranchCondGen.get_br_lt()) or
      (instr._get_instr_name_equivalence(["BGE"]) and
      not BranchCondGen.get_br_lt()) or
      (instr._get_instr_name_equivalence(["BLTU"]) and
      BranchCondGen.get_br_ltu()) or
      (instr._get_instr_name_equivalence(["BGEU"]) and
      not BranchCondGen.get_br_ltu())):  
       ControlSignals.set_pc_sel(2)
       full_display()
       continue
   elif instr._type == instrTypes.UJ:
       ControlSignals.set_pc_sel(3)
       full_display()
       continue
   else:
       ControlSignals.set_pc_sel(0)

   # select op1 and op2
   op1=op1sel_mux(ControlSignals.get_op1sel())
   op2=op2sel_mux(ControlSignals.get_op2sel())

   DataMem.exec(
       addr = ALU.alu(op1sel_mux(ControlSignals.get_op1sel()),
                      op2sel_mux(ControlSignals.get_op2sel()), 
                      ControlSignals.get_alufun()
              ),
       wdata = RegFile.get_rs2(), 
       mem_rw = ControlSignals.get_mem_rw(),
       mem_val = 4
   )

   # regfile writing
   RegFile.clock(
       wa=instr.get_rd(), 
       wd=wb_sel_mux(ControlSignals.get_wb_sel()),
       en=ControlSignals.get_rf_wen()
   )

   full_display()

   # then handle ECALL
   if _handle_ecall(): break # if instr was ecall and dictates processor
                             # stopping, i.e. halt or exit, break out of loop

   

print("Final register values")
RegFile.display()
