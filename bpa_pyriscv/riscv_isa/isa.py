from .csr_list import csrs
from .instr_codes import instrOpcode, instrFunct3, instrFunct7, instrTypes
from itype import IType
from pydigital.utils import as_twos_comp
from utype import UType
from stype import SType
from branch_targ_gen import BranchTargGen
from jump_targ_gen import JumpTargGen

class BadInstruction(Exception):
        pass

# build csr lookup
csrd = {k:v for k,v in csrs}

def regNumToName(num):
        if type(num) != int or num < 0 or num > 31:
                raise BadInstruction()
        return ['zero','ra','sp','gp',  # 0..3
            'tp', 't0', 't1', 't2', # 4..7
            's0', 's1', 'a0', 'a1', # 8..11
            'a2', 'a3', 'a4', 'a5', # 12..15
            'a6', 'a7', 's2', 's3', # 16..19
            's4', 's5', 's6', 's7', # 20..23
            's8', 's9', 's10', 's11', # 24..27]
            't3', 't4', 't5', 't6'][num] # 28..31

name_to_type = {
    instrTypes.I: ["LB", "LH", "LW", "LD", "LBU", "LHU",
                   "LWU", "FENCE", "FENCE_I", "ADDI", "SLLI", "SLTI",
                   "SLTIU", "XORI", "SRLI", "SRAI", "ORI", "ANDI",
                   "ADDIW", "SLLIW", "SRLIW", "SRAIW", "JALR", "ECALL",
                   "EBREAK", "CSRRW", "CSRRS", "CSRRC", "CSRRWI", "CSRRSI",
                   "CSRRCI"],
    instrTypes.U: ["AUIPC", "LUI"],
    instrTypes.S: ["SB", "SH", "SW", "SD"],
    instrTypes.R: ["ADD", "SUB", "SLL", "SLT", "SLTU", "XOR", "SRL",
                   "SRA", "OR", "AND", "ADDW", "SUBW", "SLLW", "SRLW",
                   "SRAW"],
    instrTypes.SB: ["BEQ", "BNE", "BLT", "BGE", "BLTU", "BGEU"],
    instrTypes.UJ: ["JAL"]                   
}


def instrNameToType(name: str):
    global name_to_type
    for key, value in name_to_type.items():
        if name.upper() in value:
            return key
    return None

class Instruction():
        "represents/decodes RISCV instructions"  

        def __init__ (self, val, pc, symbols = {}):
                """
                Decodes a risc-v instruction word
                val is the machine code word
                pc is the pc value used to format pc-relative assembly instructions
                symbols is an optional symbol table to decode addresses in assembly output 
                """
                self.val = val
                self.pc = pc # pc relative instrs need pc to compute targets for display
                self.symbols = symbols

                self._opcode = None
                self._funct3 = None
                self._funct7 = None
                self._mnemonic = None
                
                self._rd = None
                self._rs1 = None
                self._rs2 = None
                # set by imm combinational blocks, namely
                # BranchTargGen, JumpTargGen, ITypeSignExtend,
                # STypeSignExtend, and UType
                self._imm = None

                self._type = None

                self.decode_and_set_instr_components()

        get_val = lambda self: self.val

        get_opcode = lambda self: self._opcode
        get_funct3 = lambda self: self._funct3
        get_funct7 = lambda self: self._funct7
        get_mnemonic = lambda self: self._mnemonic
        
        get_rd = lambda self: self._rd
        get_rs1 = lambda self: self._rs1
        get_rs2 = lambda self: self._rs2
        get_imm = lambda self: self._imm
        
        def decode_and_set_instr_components(self):
                self._decode_and_set_mnemonic()
                self._decode_and_set_type()
                self._decode_by_type_and_set_bits()

        def _get_candidates_with_funct_3(self, instr_candidate_names):
                candidates_with_funct3 = []
                for funct3_item_name, funct3_item in instrFunct3.__members__.items():
                        for candidate_name in instr_candidate_names:
                                if funct3_item_name == candidate_name: 
                                        candidates_with_funct3.append(candidate_name)
                return candidates_with_funct3

        def _get_candidates_with_funct_7(self, instr_candidate_names):
                candidates_with_funct7 = []
                for funct7_item_name, funct7_item in instrFunct7.__members__.items():
                        for candidate_name in instr_candidate_names:
                                if funct7_item_name == candidate_name: 
                                        candidates_with_funct7.append(candidate_name)
                return candidates_with_funct7

        def _decode_and_set_mnemonic(self):
                self._decode_and_set_opcode()
                
                instr_candidate_names = [item_name for item_name, item in instrOpcode.__members__.items()]

                for opcode_item_name, opcode_item in instrOpcode.__members__.items():
                        if opcode_item.value != self._opcode:
                                instr_candidate_names.remove(
                                        opcode_item_name
                                )

                candidates_with_funct3 = self._get_candidates_with_funct_3(instr_candidate_names)
                funct3_match_found = False

                if len(candidates_with_funct3) > 0:
                        self._decode_and_set_funct3()
                        for candidate_with_funct3 in candidates_with_funct3:
                                if instrFunct3[candidate_with_funct3].value != self._funct3:
                                        instr_candidate_names.remove(
                                                candidate_with_funct3
                                        )
                                else: funct3_match_found = True

                
                candidates_with_funct7 = self._get_candidates_with_funct_7(instr_candidate_names)
                funct7_match_found = False
                
                if len(candidates_with_funct7) > 0:
                        self._decode_and_set_funct7()
                        for candidate_with_funct7 in candidates_with_funct7:
                                if instrFunct7[candidate_with_funct7].value != self._funct7:
                                        instr_candidate_names.remove(
                                                candidate_with_funct7
                                        )
                                else: funct7_match_found = True
                
                if not funct7_match_found: self._reset_funct7()
                if not funct3_match_found: self._reset_funct3()
 
                if len(instr_candidate_names) > 0:
                        self._mnemonic = instr_candidate_names[0]
                else:
                        print("No matching instructions found.")

        
        def _decode_and_set_type(self):
                self._type = instrNameToType(self._mnemonic) 

        def _decode_by_type_and_set_bits(self):
                getattr(self, "_decode_" +\
                        str(instrTypes(self._type).name.lower()) +\
                        "_instr_and_set_bits")()

        def _decode_and_set_opcode(self):
                self._opcode = self.val & 0x7f # set lower 7 bits
                                               # to opcode instruction attribute

        def _decode_and_set_rd(self):
                self._rd = (self.val >> 7) & 0x1f
        
        def _decode_and_set_funct3(self):
                self._funct3 = (self.val >> 12) & 0x7

        def _decode_and_set_rs1(self):
                self._rs1 = (self.val >> 15) & 0x1f

        def _decode_and_set_rs2(self):
                self._rs2 = (self.val >> 20) & 0x1f

        def _decode_and_set_funct7(self):
                self._funct7 = (self.val >> 25)

        def _decode_i_instr_and_set_bits(self):
                self._decode_and_set_rd()
                self._decode_and_set_funct3()
                self._decode_and_set_rs1()

        def _decode_r_instr_and_set_bits(self):
                self._decode_and_set_rd()
                self._decode_and_set_funct3()
                self._decode_and_set_rs1()
                self._decode_and_set_rs2()
                self._decode_and_set_funct7()

        def _decode_u_instr_and_set_bits(self):
                self._decode_and_set_rd()

        def _decode_s_instr_and_set_bits(self):
                self._decode_and_set_funct3()
                self._decode_and_set_rs1()
                self._decode_and_set_rs2()
 
        def _decode_sb_instr_and_set_bits(self):
                self._decode_and_set_funct3()
                self._decode_and_set_rs1()
                self._decode_and_set_rs2()

        def _decode_uj_instr_and_set_bits(self):
                self._decode_and_set_rd()

        def update_imm(self):
                if self._type == instrTypes.I: self._imm = IType.get_imm()
                if self._type == instrTypes.S: self._imm = SType.get_imm()
                if self._type == instrTypes.U: self._imm = UType.get_imm()
                if self._type == instrTypes.SB: self._imm = BranchTargGen.get_branch()
                if self._type == instrTypes.UJ: self._imm = JumpTargGen.get_jump() 
 
        def _get_instr_name_equivalence(self, instr_names: list):
                for instr_name in instr_names:    
                    if self._mnemonic.upper() == instr_name.upper():
                        return True
                return False

        def is_csr(self):
            if self._get_instr_name_equivalence(["CSRRW", "CSRRS", "CSRRC",
                                                 "CSRRWI", "CSRRSI", "CSRRCI"]):
                return True

        def __str__(self):
                str_out = str(self._mnemonic).lower() + " "
                if self._get_instr_name_equivalence(["ADDI"]): 
                    if self._rs1 == 0x0:
                        return "li " + regNumToName(self._rd) + "," +\
                               f"0x{self._imm:x}"
                if self._get_instr_name_equivalence(["ECALL"]):
                    return str_out
                if self._get_instr_name_equivalence(["ADD", "OR", "SLL", "SRL", "SRA",
                                                     "SUB", "XOR", "AND", "SLTU", "SLT"]):
                    return str_out + regNumToName(self._rd) + "," +\
                           regNumToName(self._rs1) + "," +\
                           regNumToName(self._rs2)
                if self._get_instr_name_equivalence(["ADDI", "ANDI", "ORI",
                                                     "SLTI", "SLTIU", "SLLI", 
                                                     "JALR", "XORI",
                                                     "SRAI", "SRLI"]):
                    if self._get_instr_name_equivalence(["JALR"]) and\
                       self._rd == 0x0 and self._rs1 == 0x1: 
                        return "ret"
                    return str_out + regNumToName(self._rd) + "," +\
                           regNumToName(self._rs1) + "," +\
                           f"0x{self._imm:x}"
                if self._get_instr_name_equivalence(["BEQ", "BNE", "BLT", "BLTU",
                                                       "BGE", "BGEU"]):
                    if self._rs2 == 0x0:
                        return str(self._mnemonic).lower() + "z " + regNumToName(self._rs1) +\
                               "," + f"0x{as_twos_comp(self._imm):x}"
                    return str_out + regNumToName(self._rs1) + "," +\
                           regNumToName(self._rs2) + "," +\
                           f"0x{self._imm:x}"
                if self._get_instr_name_equivalence(["JAL"]):
                    if self._rd == 0x0:
                        return "j " + f"{self._imm:x}"
                    return str_out + regNumToName(self._rd) + "," +\
                           f"0x{self._imm:x}"
                if self._get_instr_name_equivalence(["LB", "LH", "LW", "LBU", "LHU", "LWU"]):
                    return str_out + regNumToName(self._rd) + "," +\
                           f"0x{self._imm:x}" + f"({regNumToName(self._rs1)})"
                if self._get_instr_name_equivalence(["SB", "SH", "SW"]):
                    return str_out + regNumToName(self._rs2) + "," +\
                           f"0x{self._imm:x}" + f"({regNumToName(self._rs1)})"
                if self.is_csr() or self._get_instr_name_equivalence(["FENCE"]):
                    return str_out + " instruction"

                # added by Marchiori
                if self._get_instr_name_equivalence(["LUI"]):
                    return str_out + regNumToName(self._rd) + f",0x{(0xfffff000 & self.val)>>12:05x}"
                if self._get_instr_name_equivalence(["AUIPC"]):
                    return str_out + regNumToName(self._rd) + "," +\
                           f"0x{self._imm:x}"
                raise Exception(f"Cannot decode instruction {self._mnemonic} at this time.")

        def _reset_instr_components(self):
                self._opcode = None
                self._funct3 = None
                self._funct7 = None
                self._mnemonic = None
                
                self._rd = None
                self._rs1 = None
                self._rs2 = None
                self._imm = None
                        
                self._type = None

        def _reset_funct3(self):
                self._funct3 = None

        def _reset_funct7(self):
                self._funct7 = None
                
 
