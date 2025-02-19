from veriloggen import *
from math import ceil, log2
from src.old.python.util.hw_components import HwComponents
from src.old.python.util.hw_util import HwUtil
from src.old.python.util.per_enum import ArchType
from src.old.python.util.per_graph import PeRGraph
from src.old.python.util.piplinebase import PiplineBase
from src.old.python.util.util import Util


class YottPipelineHw(PiplineBase):
    def __init__(self, per_graph: PeRGraph, arch_type: ArchType, distance_table_bits: int, make_shuffle: bool,
                 n_threads: int = 10, n_annotations: int = 3):
        self.len_pipeline: int = 10
        super().__init__(per_graph, arch_type, distance_table_bits, make_shuffle, self.len_pipeline, n_threads, )
        self.hw_components = HwComponents()
        self.th_bits = Util.get_n_bits(self.n_threads)
        self.edge_bits = Util.get_n_bits(self.per_graph.n_cells)
        self.node_bits = Util.get_n_bits(self.per_graph.n_cells)
        self.ij_bits = Util.get_n_bits(self.n_lines)
        self.total_dists = pow((self.n_lines * 2) - 1, 2)
        self.dst_counter_bits = 6
        self.fifo_width = self.th_bits + 1
        self.fifo_depth_bits = self.th_bits + 1
        self.n_annotations = n_annotations
        self.dist_bits = ceil(log2(self.n_lines + self.n_columns))
        # fixme uncomment the line below and comment the line above
        # self.dst_counter_bits = Util.get_n_bits(self.total_dists) + 1

    def create_rom_files(self, edges_rom_f: str, n2c_rom_f: str, dst_tbl_rom_f: str,
                         cell_content_f: str, ann_rom_f, n2c: list[list[list]], annotations: list[list[list[int]]]):
        # Function to create ROM content
        # edges rom file
        edges_file_bits = self.node_bits * 2
        edges_addr_bits = self.th_bits + self.edge_bits
        edges_file_content = ['{0:b}'.format(0).zfill(edges_file_bits) for _ in range(pow(2, edges_addr_bits))]
        for th, edges in enumerate(self.edges_int):
            for edg_idx, edge in enumerate(edges):
                idx: int = th << self.edge_bits | edg_idx
                idx_s: str = '{0:b}'.format(idx).zfill(edges_addr_bits)
                edg_content = edge[0] << self.node_bits | edge[1]
                edges_file_content[idx] = '{0:b}'.format(edg_content).zfill(edges_file_bits)

        # dst_table rom file
        dst_table_file_bits = 2 * (self.ij_bits + 1)
        dst_table_addr_bits = self.distance_table_bits + self.dst_counter_bits - 1
        dst_table_file_content = ['{0:b}'.format(0).zfill(dst_table_file_bits) for _ in
                                  range(pow(2, dst_table_addr_bits))]
        dst_table: list[list[list]] = [
            Util.get_distance_table(self.arch_type, self.n_lines, self.make_shuffle) for _ in
            range(pow(2, self.distance_table_bits))]
        for line_idx, lcs in enumerate(dst_table):
            for lc_idx, lc in enumerate(lcs):
                lc0, lc1 = lc
                mask = (pow(2, self.ij_bits + 1) - 1)
                if lc0 < 0:
                    lc0 = ((lc0 * -1) ^ mask) + 1
                if lc1 < 0:
                    lc1 = ((lc1 * -1) ^ mask) + 1

                idx: int = line_idx << (self.dst_counter_bits - 1) | lc_idx
                idx_s: str = '{0:b}'.format(idx).zfill(dst_table_addr_bits)

                dst_table_content = lc0 << (self.ij_bits + 1) | lc1
                dst_table_file_content[idx] = '{0:b}'.format(dst_table_content).zfill(dst_table_file_bits)

        # cell content rom file
        cell_content_file_bits = 1
        cell_content_addr_bits = self.th_bits + 2 * self.ij_bits
        cell_content_file_content = ['{0:b}'.format(0).zfill(cell_content_file_bits) for _ in
                                     range(pow(2, cell_content_addr_bits))]

        # n2c rom file
        n2c_file_bits = 2 * self.ij_bits
        n2c_addr_bits = self.th_bits + self.node_bits
        n2c_file_content = ['{0:b}'.format(0).zfill(n2c_file_bits) for _ in range(pow(2, n2c_addr_bits))]

        for th, n2cs in enumerate(n2c):
            for ann_idx, n2c_ in enumerate(n2cs):
                if n2c_[0] is None:
                    continue
                n2c_idx: int = th << self.node_bits | ann_idx
                n2c_idx_s: str = '{0:b}'.format(n2c_idx).zfill(n2c_addr_bits)
                n2c_content = n2c_[0] << self.ij_bits | n2c_[1]
                n2c_file_content[n2c_idx] = '{0:b}'.format(n2c_content).zfill(n2c_file_bits)

                cell_content_idx: int = th << (2 * self.ij_bits) | n2c_[0] << self.ij_bits | n2c_[1]
                cell_content_idx_str: str = '{0:b}'.format(cell_content_idx).zfill(cell_content_addr_bits)
                cell_content = 1
                cell_content_file_content[cell_content_idx] = '{0:b}'.format(cell_content).zfill(cell_content_file_bits)
                break

        # create annotations rom content
        ann_file_bits = (self.node_bits + self.dist_bits + 1) * 3
        ann_addr_bits = self.th_bits + self.edge_bits
        ann_file_content = ['{0:b}'.format(pow(2, (self.node_bits + self.dist_bits + 1) * 3) - 1).zfill(ann_file_bits)
                            for _ in range(pow(2, ann_addr_bits))]
        ann_mask = pow(2, (self.node_bits + self.dist_bits + 1)) - 1
        for th_idx, anns in enumerate(annotations):
            for edge_idx, edge_ann in enumerate(anns):
                ann_value = 0
                ann_value_str = ''
                for ann_idx, ann in enumerate(edge_ann):
                    ann_value = ann_value << (self.node_bits + self.dist_bits + 1)
                    if -1 in ann:
                        ann_value = ann_value | ann_mask
                    else:
                        ann_value = ann_value | (ann[0] << self.dist_bits | ann[1])
                ann_value_str = '{0:b}'.format(ann_value).zfill(ann_file_bits)
                ann_file_idx = (th_idx << self.edge_bits) | edge_idx
                ann_file_content[ann_file_idx] = ann_value_str

        Util.write_file(edges_rom_f, edges_file_content)
        Util.write_file(dst_tbl_rom_f, dst_table_file_content)
        Util.write_file(n2c_rom_f, n2c_file_content)
        Util.write_file(cell_content_f, cell_content_file_content)
        Util.write_file(ann_rom_f, ann_file_content)

    def create_yott_pipeline_hw(self, edges_rom_f: str, annotations_rom_f: str, n2c_rom_f: str, dst_tbl_rom_f: str,
                                cell_content_f: str, simulate: bool) -> Module:
        name = "yott_pipeline_hw"
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')
        start = m.Input('start')
        visited_edges = m.Input('visited_edges', self.edge_bits)
        done = m.Output('done')

        st2_conf_wr0 = m.Input('st2_conf_wr0')
        st2_conf_addr0 = m.Input('st2_conf_addr0', self.edge_bits + self.th_bits)
        st2_conf_data0 = m.Input('st2_conf_data0', self.node_bits * 2)
        st2_conf_wr1 = m.Input('st2_conf_wr1')
        st2_conf_addr1 = m.Input('st2_conf_addr1', self.th_bits + self.edge_bits)
        st2_conf_data1 = m.Input('st2_conf_data1', (self.node_bits + self.dist_bits + 1) * 3)
        st3_conf_wr = m.Input('st3_conf_wr')
        st3_conf_wr_addr = m.Input('st3_conf_wr_addr', self.th_bits + self.node_bits)
        st3_conf_wr_data = m.Input('st3_conf_wr_data', self.ij_bits * 2)
        st3_conf_rd = m.Input('st3_conf_rd')
        st3_conf_rd_addr = m.Input('st3_conf_rd_addr', self.th_bits + self.node_bits)
        st3_conf_rd_data = m.Output('st3_conf_rd_data', self.ij_bits * 2)
        st4_conf_wr = m.Input('st4_conf_wr')
        st4_conf_addr = m.Input('st4_conf_addr', self.dst_counter_bits - 1 + self.distance_table_bits)
        st4_conf_data = m.Input('st4_conf_data', (self.ij_bits + 1) * 2)
        st7_conf_wr = m.Input('st7_conf_wr')
        st7_conf_addr = m.Input('st7_conf_addr', self.th_bits + self.ij_bits * 2)
        st7_conf_data = m.Input('st7_conf_data')

        start_pipeline = m.Reg('start_pipeline')
        init_fifo = m.Reg('init_fifo')
        thread_counter = m.Reg('thread_counter', self.th_bits)

        fsm_init_fifo = m.Reg('fsm_init_fifo', 3)
        init = m.Localparam('init', Int(0, fsm_init_fifo.width, 10))
        wait_init = m.Localparam('wait_init', Int(1, fsm_init_fifo.width, 10))
        start_p = m.Localparam('start_p', Int(2, fsm_init_fifo.width, 10))

        m.Always(Posedge(clk))(
            If(rst)(
                start_pipeline(Int(0, 1, 10)),
                thread_counter(Int(0, thread_counter.width, 10)),
                init_fifo(Int(0, 1, 10)),
                fsm_init_fifo(init),
            ).Elif(start)(
                Case(fsm_init_fifo)(
                    When(init)(
                        init_fifo(Int(1, 1, 10)),
                        fsm_init_fifo(wait_init),
                    ),
                    When(wait_init)(
                        If(thread_counter == Int(self.n_threads - 1, thread_counter.width, 10))(
                            init_fifo(Int(0, 1, 10)),
                            fsm_init_fifo(start_p),
                        ),
                        thread_counter(thread_counter + Int(1, thread_counter.width, 10))
                    ),
                    When(start_p)(
                        start_pipeline(Int(1, 1, 10))
                    )
                ),

            )
        )

        m.EmbeddedCode('// St0 wires')
        st0_thread_index = m.Wire('st0_thread_index', self.th_bits)
        st0_thread_valid = m.Wire('st0_thread_valid')
        st0_should_write = m.Wire('st0_should_write')
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St1 wires')
        st1_thread_index = m.Wire('st1_thread_index', self.th_bits)
        st1_thread_valid = m.Wire('st1_thread_valid')
        st1_edge_index = m.Wire('st1_edge_index', self.edge_bits)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St2 wires')
        st2_thread_index = m.Wire('st2_thread_index', self.th_bits)
        st2_thread_valid = m.Wire('st2_thread_valid')
        st2_a = m.Wire('st2_a', self.node_bits)
        st2_b = m.Wire('st2_b', self.node_bits)
        st2_cs = m.Wire('st2_cs', (self.node_bits + 1) * 3)
        st2_dist_csb = m.Wire('st2_dist_csb', self.dist_bits * 3)
        st2_index_list_edge = m.Wire('st2_index_list_edge', self.distance_table_bits)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St3 wires')
        st3_thread_index = m.Wire('st3_thread_index', self.th_bits)
        st3_thread_valid = m.Wire('st3_thread_valid')
        st3_c_a = m.Wire('st3_c_a', self.ij_bits * 2)
        st3_b = m.Wire('st3_b', self.node_bits)
        st3_cs_c = m.Wire('st3_cs_c', (self.ij_bits * 2 + 1) * 3)
        st3_dist_csb = m.Wire('st3_dist_csb', self.dist_bits * 3)
        st3_adj_index = m.Wire('st3_adj_index', self.dst_counter_bits)
        st3_index_list_edge = m.Wire('st3_index_list_edge', self.distance_table_bits)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St4 wires')
        st4_thread_index = m.Wire('st4_thread_index', self.th_bits)
        st4_thread_valid = m.Wire('st4_thread_valid')
        st4_c_a = m.Wire('st4_c_a', self.ij_bits * 2)
        st4_b = m.Wire('st4_b', self.node_bits)
        st4_c_s = m.Wire('st4_c_s', (self.ij_bits) * 2)
        st4_cs_c = m.Wire('st4_cs_c', (self.ij_bits * 2 + 1) * 3)
        st4_dist_csb = m.Wire('st4_dist_csb', self.dist_bits * 3)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St5 wires')
        st5_thread_index = m.Wire('st5_thread_index', self.th_bits)
        st5_thread_valid = m.Wire('st5_thread_valid')
        st5_b = m.Wire('st5_b', self.node_bits)
        st5_c_s = m.Wire('st5_c_s', (self.ij_bits) * 2)
        st5_cs_c = m.Wire('st5_cs_c', (self.ij_bits * 2 + 1) * 3)
        st5_dist_csb = m.Wire('st5_dist_csb', self.dist_bits * 3)
        st5_dist_ca_cs = m.Wire('st5_dist_ca_cs', self.dist_bits)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St6 wires')
        st6_thread_index = m.Wire('st6_thread_index', self.th_bits)
        st6_thread_valid = m.Wire('st6_thread_valid')
        st6_b = m.Wire('st6_b', self.node_bits)
        st6_c_s = m.Wire('st6_c_s', self.ij_bits * 2)
        st6_cost = m.Wire('st6_cost', self.dist_bits + 2)
        st6_dist_ca_cs = m.Wire('st6_dist_ca_cs', self.dist_bits)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St7 wires')
        st7_thread_index = m.Wire('st7_thread_index', self.th_bits)
        st7_thread_valid = m.Wire('st7_thread_valid')
        st7_b = m.Wire('st7_b', self.node_bits)
        st7_c_s = m.Wire('st7_c_s', self.ij_bits * 2)
        st7_cost = m.Wire('st7_cost', self.dist_bits + 2)
        st7_dist_ca_cs = m.Wire('st7_dist_ca_cs', self.dist_bits)
        st7_cell_free = m.Wire('st7_cell_free')
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St8 wires')
        st8_thread_index = m.Wire('st8_thread_index', self.th_bits)
        st8_thread_valid = m.Wire('st8_thread_valid')
        st8_b = m.Wire('st8_b', self.node_bits)
        st8_c_s = m.Wire('st8_c_s', self.ij_bits * 2)
        st8_cost = m.Wire('st8_cost', self.dist_bits + 2)
        st8_dist_ca_cs = m.Wire('st8_dist_ca_cs', self.dist_bits)
        st8_save_cell = m.Wire('st8_save_cell')
        st8_should_write = m.Wire('st8_should_write')
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St9 wires')
        st9_thread_index = m.Wire('st9_thread_index', self.th_bits)
        st9_thread_valid = m.Wire('st9_thread_valid')
        st9_should_write = m.Wire('s9_should_write')
        st9_b = m.Wire('st9_b', self.node_bits)
        st9_c_s = m.Wire('st9_c_s', self.ij_bits * 2)
        st9_write_enable = m.Wire('st9_write_enable')
        st9_input_data = m.Wire('st9_input_data', self.fifo_width)
        m.EmbeddedCode('// -----')
        m.EmbeddedCode('')

        m.EmbeddedCode('// St0 instantiation')
        stage0_m = self.create_stage0_yott()
        par = []
        con = [
            ('clk', clk),
            ('rst', rst),
            ('start', start_pipeline),
            ('thread_index', st0_thread_index),
            ('thread_valid', st0_thread_valid),
            ('should_write', st0_should_write),
            ('st9_write_enable', Mux(init_fifo, Int(1, 1, 10), st9_write_enable)),
            ('st9_input_data', Mux(init_fifo, Cat(thread_counter, Int(0, 1, 10)), st9_input_data)),
        ]
        m.Instance(stage0_m, stage0_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St1 instantiation')
        stage1_m = self.create_stage1_yott()
        con = [
            ('clk', clk),
            ('rst', rst),
            ('st0_thread_index', st0_thread_index),
            ('st0_thread_valid', st0_thread_valid),
            ('st0_should_write', st0_should_write),
            ('visited_edges', visited_edges),
            ('thread_index', st1_thread_index),
            ('thread_valid', st1_thread_valid),
            ('edge_index', st1_edge_index),
            ('done', done),
        ]
        m.Instance(stage1_m, stage1_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St2 instantiation')
        stage2_m = self.create_stage2_yott(edges_rom_f, annotations_rom_f, simulate)
        con = [
            ('clk', clk),
            ('rst', rst),
            ('st1_thread_index', st1_thread_index),
            ('st1_thread_valid', st1_thread_valid),
            ('st1_edge_index', st1_edge_index),
            ('thread_index', st2_thread_index),
            ('thread_valid', st2_thread_valid),
            ('a', st2_a),
            ('b', st2_b),
            ('cs', st2_cs),
            ('dist_csb', st2_dist_csb),
            ('index_list_edge', st2_index_list_edge),
            ('conf_wr0', st2_conf_wr0),
            ('conf_addr0', st2_conf_addr0),
            ('conf_data0', st2_conf_data0),
            ('conf_wr1', st2_conf_wr1),
            ('conf_addr1', st2_conf_addr1),
            ('conf_data1', st2_conf_data1),
        ]
        m.Instance(stage2_m, stage2_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St3 instantiation')
        stage3_m = self.create_stage3_yott(n2c_rom_f, simulate)
        con = [
            ('clk', clk),
            ('rst', rst),
            ('st2_thread_index', st2_thread_index),
            ('st2_thread_valid', st2_thread_valid),
            ('st2_a', st2_a),
            ('st2_b', st2_b),
            ('st2_cs', st2_cs),
            ('st2_dist_csb', st2_dist_csb),
            ('st2_index_list_edge', st2_index_list_edge),
            ('thread_index', st3_thread_index),
            ('thread_valid', st3_thread_valid),
            ('c_a', st3_c_a),
            ('b', st3_b),
            ('cs_c', st3_cs_c),
            ('dist_csb', st3_dist_csb),
            ('adj_index', st3_adj_index),
            ('index_list_edge', st3_index_list_edge),
            ('st9_thread_index', st9_thread_index),
            ('st9_thread_valid', st9_thread_valid),
            ('s9_should_write', st9_should_write),
            ('st9_b', st9_b),
            ('st9_c_s', st9_c_s),
            ('conf_wr', st3_conf_wr),
            ('conf_wr_addr', st3_conf_wr_addr),
            ('conf_wr_data', st3_conf_wr_data),
            ('conf_rd', st3_conf_rd),
            ('conf_rd_addr', st3_conf_rd_addr),
            ('conf_rd_data', st3_conf_rd_data),
        ]
        m.Instance(stage3_m, stage3_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St4 instantiation')
        stage4_m = self.create_stage4_yott(dst_tbl_rom_f, simulate)
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st4_thread_index),
            ('thread_valid', st4_thread_valid),
            ('c_a', st4_c_a),
            ('b', st4_b),
            ('c_s', st4_c_s),
            ('cs_c', st4_cs_c),
            ('dist_csb', st4_dist_csb),
            ('st3_thread_index', st3_thread_index),
            ('st3_thread_valid', st3_thread_valid),
            ('st3_c_a', st3_c_a),
            ('st3_b', st3_b),
            ('st3_cs_c', st3_cs_c),
            ('st3_dist_csb', st3_dist_csb),
            ('st3_adj_index', st3_adj_index),
            ('st3_index_list_edge', st3_index_list_edge),
            ('conf_wr', st4_conf_wr),
            ('conf_addr', st4_conf_addr),
            ('conf_data', st4_conf_data),
        ]
        m.Instance(stage4_m, stage4_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St5 instantiation')
        stage5_m = self.create_stage5_yott()
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st5_thread_index),
            ('thread_valid', st5_thread_valid),
            ('b', st5_b),
            ('c_s', st5_c_s),
            ('cs_c', st5_cs_c),
            ('dist_csb', st5_dist_csb),
            ('dist_ca_cs', st5_dist_ca_cs),
            ('st4_thread_index', st4_thread_index),
            ('st4_thread_valid', st4_thread_valid),
            ('st4_c_a', st4_c_a),
            ('st4_b', st4_b),
            ('st4_c_s', st4_c_s),
            ('st4_cs_c', st4_cs_c),
            ('st4_dist_csb', st4_dist_csb),
        ]
        m.Instance(stage5_m, stage5_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St6 instantiation')
        stage6_m = self.create_stage6_yott()
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st6_thread_index),
            ('thread_valid', st6_thread_valid),
            ('b', st6_b),
            ('c_s', st6_c_s),
            ('cost', st6_cost),
            ('dist_ca_cs', st6_dist_ca_cs),
            ('st5_thread_index', st5_thread_index),
            ('st5_thread_valid', st5_thread_valid),
            ('st5_b', st5_b),
            ('st5_c_s', st5_c_s),
            ('st5_cs_c', st5_cs_c),
            ('st5_dist_csb', st5_dist_csb),
            ('st5_dist_ca_cs', st5_dist_ca_cs),
        ]
        m.Instance(stage6_m, stage6_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St7 instantiation')
        stage7_m = self.create_stage7_yott(cell_content_f, simulate)
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st7_thread_index),
            ('thread_valid', st7_thread_valid),
            ('b', st7_b),
            ('c_s', st7_c_s),
            ('cost', st7_cost),
            ('dist_ca_cs', st7_dist_ca_cs),
            ('cell_free', st7_cell_free),
            ('st6_thread_index', st6_thread_index),
            ('st6_thread_valid', st6_thread_valid),
            ('st6_b', st6_b),
            ('st6_c_s', st6_c_s),
            ('st6_cost', st6_cost),
            ('st6_dist_ca_cs', st6_dist_ca_cs),
            ('st9_thread_index', st9_thread_index),
            ('s9_should_write', st9_should_write),
            ('st9_c_s', st9_c_s),
            ('conf_wr', st7_conf_wr),
            ('conf_addr', st7_conf_addr),
            ('conf_data', st7_conf_data),
        ]
        m.Instance(stage7_m, stage7_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St8 instantiation')
        stage8_m = self.create_stage8_yott()
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st8_thread_index),
            ('thread_valid', st8_thread_valid),
            ('b', st8_b),
            ('c_s', st8_c_s),
            ('cost', st8_cost),
            ('dist_ca_cs', st8_dist_ca_cs),
            ('save_cell', st8_save_cell),
            ('should_write', st8_should_write),
            ('st7_thread_index', st7_thread_index),
            ('st7_thread_valid', st7_thread_valid),
            ('st7_b', st7_b),
            ('st7_c_s', st7_c_s),
            ('st7_cost', st7_cost),
            ('st7_dist_ca_cs', st7_dist_ca_cs),
            ('st7_cell_free', st7_cell_free),
        ]
        m.Instance(stage8_m, stage8_m.name, par, con)
        m.EmbeddedCode('// -----')

        m.EmbeddedCode('// St9 instantiation')
        stage9_m = self.create_stage9_yott()
        con = [
            ('clk', clk),
            ('rst', rst),
            ('thread_index', st9_thread_index),
            ('thread_valid', st9_thread_valid),
            ('b', st9_b),
            ('c_s', st9_c_s),
            ('should_write', st9_should_write),
            ('write_enable', st9_write_enable),
            ('input_data', st9_input_data),
            ('st8_thread_index', st8_thread_index),
            ('st8_thread_valid', st8_thread_valid),
            ('st8_b', st8_b),
            ('st8_c_s', st8_c_s),
            ('st8_cost', st8_cost),
            ('st8_dist_ca_cs', st8_dist_ca_cs),
            ('st8_save_cell', st8_save_cell),
            ('st8_should_write', st8_should_write),
        ]
        m.Instance(stage9_m, stage9_m.name, par, con)
        m.EmbeddedCode('// -----')

        HwUtil.initialize_regs(m)
        return m

    def create_yott_pipeline_hw_test_bench(self, v_output_base: str, simulate: bool):
        base_file_name = f'{v_output_base}{self.per_graph.dot_name.replace(".", "_")}'
        edges_rom_f: str = f'{base_file_name}_edges.rom'
        n2c_rom_f: str = f'{base_file_name}_n2c.rom'
        ann_rom_f: str = f'{base_file_name}_ann_rom.rom'
        dst_tbl_rom_f: str = f'{base_file_name}_dst_tbl.rom'
        cell_content_f: str = f'{base_file_name}_cell_content.rom'
        dump_f: str = f'{v_output_base}{self.per_graph.dot_name}.vcd'
        run_file: str = f'{base_file_name}.out'

        first_nodes: list = [self.edges_int[i][0][0] for i in range(self.len_pipeline)]
        n2c, c2n = self.init_traversal_placement_tables(first_nodes)
        annotations = []
        for ann in self.annotations:
            tmp = list(ann.values())
            for idx, t in enumerate(tmp):
                while len(t) < 3:
                    t.append([-1, -1])
                t = t[0:3]
                t = [(self.per_graph.nodes_to_idx[t_t[0]], t_t[1] + 1) if (
                        t_t[0] != -1 and t_t[1] < 3) else [-1, -1] for t_t in t]
                tmp[idx] = t
            annotations.append(tmp)

        self.create_rom_files(edges_rom_f, n2c_rom_f, dst_tbl_rom_f, cell_content_f, ann_rom_f, n2c, annotations)

        name = '%s_yott_pip_hw_test_bench' % self.per_graph.dot_name.replace(".", "_")
        m = Module(name)

        clk = m.Reg('clk')
        rst = m.Reg('rst')
        start = m.Reg('start')

        m.EmbeddedCode('')
        yott_visited_edges = m.Wire('yott_visited_edges', self.edge_bits)
        yott_done = m.Wire('yott_done')
        yott_total_pipeline_counter = m.Wire('yott_total_pipeline_counter', 32)

        m.EmbeddedCode('')
        yott_visited_edges.assign(Int(self.visited_edges, self.edge_bits, 10))

        par = []
        con = [
            ('clk', clk),
            ('rst', rst),
            ('start', start),
            ('visited_edges', yott_visited_edges),
            ('done', yott_done),
            ('st2_conf_wr0', Int(0, 1, 10)),
            ('st2_conf_wr1', Int(0, 1, 10)),
            ('st3_conf_wr', Int(0, 1, 10)),
            ('st3_conf_rd', Int(0, 1, 10)),
            ('st4_conf_wr', Int(0, 1, 10)),
            ('st7_conf_wr', Int(0, 1, 10)),
        ]
        yott = self.create_yott_pipeline_hw(edges_rom_f, ann_rom_f, n2c_rom_f, dst_tbl_rom_f, cell_content_f, simulate)
        m.Instance(yott, yott.name, par, con)
        HwUtil.initialize_regs(m, {'clk': 0, 'rst': 1, 'start': 0})

        simulation.setup_waveform(m, dumpfile=dump_f)
        m.Initial(
            EmbeddedCode('@(posedge clk);'),
            EmbeddedCode('@(posedge clk);'),
            EmbeddedCode('@(posedge clk);'),
            rst(0),
            start(1),
            Delay(10000),
            Finish(),
        )
        m.EmbeddedCode('always #5clk=~clk;')
        m.Always(Posedge(clk))(
            If(yott_done)(
                Display('ACC DONE!'),
                Finish()
            )
        )

        verilog_f: str = f'{v_output_base}{m.name}.v'
        m.to_verilog(verilog_f)

        # sim = simulation.Simulator(m, sim='iverilog')
        # rslt = sim.run(outputfile=run_file)
        # print(rslt)

    def create_manhattan_dist_table(self) -> Module:
        name = 'distance_table'
        m = Module(name)

        source = m.Input('source', 2 * self.ij_bits)
        target1 = m.Input('target1', 2 * self.ij_bits)
        target2 = m.Input('target2', 2 * self.ij_bits)
        target3 = m.Input('target3', 2 * self.ij_bits)
        d1 = m.Output('d1', self.dist_bits)
        d2 = m.Output('d2', self.dist_bits)
        d3 = m.Output('d3', self.dist_bits)

        s_l = m.Wire('s_l', self.ij_bits)
        s_c = m.Wire('s_c', self.ij_bits)
        t1_l = m.Wire('t1_l', self.ij_bits)
        t1_c = m.Wire('t1_c', self.ij_bits)
        t2_l = m.Wire('t2_l', self.ij_bits)
        t2_c = m.Wire('t2_c', self.ij_bits)
        t3_l = m.Wire('t3_l', self.ij_bits)
        t3_c = m.Wire('t3_c', self.ij_bits)

        m.EmbeddedCode('')
        dist_table = m.Wire('dist_table', self.ij_bits, Power(2, self.ij_bits * 2))

        m.EmbeddedCode('')
        s_l.assign(source[0:self.ij_bits])
        s_c.assign(source[self.ij_bits:self.ij_bits * 2])
        t1_l.assign(target1[0:self.ij_bits])
        t1_c.assign(target1[self.ij_bits:self.ij_bits * 2])
        t2_l.assign(target2[0:self.ij_bits])
        t2_c.assign(target2[self.ij_bits:self.ij_bits * 2])
        t3_l.assign(target3[0:self.ij_bits])
        t3_c.assign(target3[self.ij_bits:self.ij_bits * 2])

        m.EmbeddedCode('')
        d1.assign(dist_table[Cat(s_l, t1_l)] + dist_table[Cat(s_c, t1_c)])
        d2.assign(dist_table[Cat(s_l, t2_l)] + dist_table[Cat(s_c, t2_c)])
        d3.assign(dist_table[Cat(s_l, t3_l)] + dist_table[Cat(s_c, t3_c)])

        m.EmbeddedCode('')
        for i in range(self.n_lines):
            for j in range(self.n_lines):
                dist_table[(i << self.ij_bits) | j].assign(Int(abs(i - j), self.dist_bits, 10))

        HwUtil.initialize_regs(m)
        return m

    def create_stage0_yott(self) -> Module:
        name = 'stage0_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')
        start = m.Input('start')

        thread_index = m.Output('thread_index', self.th_bits)
        thread_valid = m.Output('thread_valid')
        should_write = m.Output('should_write')

        st9_write_enable = m.Input('st9_write_enable')
        st9_input_data = m.Input('st9_input_data', self.fifo_width)

        fifo_output_read_enable = m.Reg('fifo_output_read_enable')
        fifo_output_valid = m.Wire('fifo_output_valid')
        fifo_output_data = m.Wire('fifo_output_data', self.fifo_width)
        fifo_empty = m.Wire('fifo_empty')
        fifo_almostempty = m.Wire('fifo_almostempty')
        fifo_full = m.Wire('fifo_full')
        fifo_almostfull = m.Wire('fifo_almostfull')
        fifo_data_count = m.Wire('fifo_data_count', self.fifo_depth_bits + 1)

        flag_wait = m.Reg('flag_wait')

        m.EmbeddedCode('')
        thread_index.assign(fifo_output_data[1:self.fifo_width])
        thread_valid.assign(fifo_output_valid)
        should_write.assign(fifo_output_data[0])

        m.Always(Posedge(clk))(
            If(rst)(
                fifo_output_read_enable(Int(0, 1, 2)),
                flag_wait(Int(0, 1, 2)),
            ).Elif(start)(
                fifo_output_read_enable(Int(0, 1, 2)),
                If(~fifo_empty)(
                    If(fifo_almostempty)(
                        If(~flag_wait)(
                            fifo_output_read_enable(Int(1, 1, 2)),
                        ),
                        flag_wait(~flag_wait)
                    ).Else(
                        fifo_output_read_enable(Int(1, 1, 2))
                    )
                ),
            )
        )

        par = [
            ('FIFO_WIDTH', self.fifo_width),
            ('FIFO_DEPTH_BITS', self.fifo_depth_bits),
            ('FIFO_ALMOSTFULL_THRESHOLD', Power(2, self.fifo_depth_bits) - 4),
            ('FIFO_ALMOSTEMPTY_THRESHOLD', 4),
        ]

        con = [
            ('clk', clk),
            ('rst', rst),
            ('write_enable', st9_write_enable),
            ('input_data', st9_input_data),
            ('output_read_enable', fifo_output_read_enable),
            ('output_valid', fifo_output_valid),
            ('output_data', fifo_output_data),
            ('empty', fifo_empty),
            ('almostempty', fifo_almostempty),
            ('full', fifo_full),
            ('almostfull', fifo_almostfull),
            ('data_count', fifo_data_count),
        ]
        fifo = self.hw_components.create_fifo()
        m.Instance(fifo, fifo.name, par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage1_yott(self) -> Module:
        name = 'stage1_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        st0_thread_index = m.Input('st0_thread_index', self.th_bits)
        st0_thread_valid = m.Input('st0_thread_valid')
        st0_should_write = m.Input('st0_should_write')
        visited_edges = m.Input('visited_edges', self.edge_bits)

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        edge_index = m.OutputReg('edge_index', self.edge_bits)

        done = m.OutputReg('done')

        thread_done = m.Reg('thread_done', self.n_threads)
        edges_indexes = m.Reg('edges_indexes', self.edge_bits, self.n_threads)
        next_edge_index = m.Wire('next_edge_index', self.edge_bits)
        done_flag = m.Wire('done_flag')

        running = m.Reg('running')

        m.EmbeddedCode('')
        next_edge_index.assign(edges_indexes[thread_index] + Cat(Int(0, edge_index.width - 1, 10), st0_should_write))
        done_flag.assign(next_edge_index == visited_edges)

        m.Always(Posedge(clk))(
            If(rst)(
                edge_index(Int(0, edge_index.width, 10)),
                thread_done(Int(0, thread_done.width, 10)),
                running(Int(0, 1, 10)),
                done(Int(0, 1, 10)),
                thread_valid(Int(0, 1, 10)),
            ).Else(
                thread_valid(st0_thread_valid),
                thread_index(st0_thread_index),
                If(st0_thread_valid)(
                    If(AndList(st0_thread_index == Int(self.n_threads - 1, st0_thread_index.width, 10)))(
                        running(Int(1, 1, 10)),
                    ),
                    If(~running)(
                        edges_indexes[st0_thread_index](Int(0, self.edge_bits + 1, 10)),
                    ).Else(
                        edges_indexes[st0_thread_index](next_edge_index),
                        edge_index(next_edge_index)
                    ),
                    If(done_flag)(
                        thread_done[st0_thread_index](Int(1, 1, 10)),
                        thread_valid(Int(0, 1, 10)),
                    ),
                    If(Uand(thread_done))(
                        done(Int(1, 1, 10)),
                    )
                ),
            )
        )

        HwUtil.initialize_regs(m)
        return m

    def create_stage2_yott(self, edges_rom_f: str, annotations_rom_f: str, simulate: bool) -> Module:
        name = 'stage2_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        st1_thread_index = m.Input('st1_thread_index', self.th_bits)
        st1_thread_valid = m.Input('st1_thread_valid')
        st1_edge_index = m.Input('st1_edge_index', self.edge_bits)

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        a = m.OutputReg('a', self.node_bits)
        b = m.OutputReg('b', self.node_bits)
        cs = m.OutputReg('cs', (self.node_bits + 1) * 3)
        dist_csb = m.OutputReg('dist_csb', self.dist_bits * 3)
        index_list_edge = m.OutputReg('index_list_edge', self.distance_table_bits)

        # configuration inputs
        conf_wr0 = m.Input('conf_wr0')
        conf_addr0 = m.Input('conf_addr0', self.edge_bits + self.th_bits)
        conf_data0 = m.Input('conf_data0', self.node_bits * 2)
        conf_wr1 = m.Input('conf_wr1')
        conf_addr1 = m.Input('conf_addr1', self.th_bits + self.edge_bits)
        conf_data1 = m.Input('conf_data1', (self.node_bits + self.dist_bits + 1) * 3)

        a_t = m.Wire('a_t', self.node_bits)
        b_t = m.Wire('b_t', self.node_bits)
        cs_t = m.Wire('cs_t', (self.node_bits + 1) * 3)
        dist_csb_t = m.Wire('dist_csb_t', self.dist_bits * 3)
        ann_out = m.Wire('ann_out', (self.node_bits + self.dist_bits + 1) * 3)

        for i in range(3):
            cs_t[i * (self.node_bits + 1):
                 (i + 1) * (self.node_bits + 1)].assign(
                ann_out[i * (self.node_bits + self.dist_bits + 1) + self.dist_bits:
                        (i + 1) * (self.node_bits + self.dist_bits + 1)])
        for i in range(3):
            dist_csb_t[i * self.dist_bits:
                       (i + 1) * self.dist_bits].assign(
                ann_out[i * (self.node_bits + self.dist_bits + 1):
                        i * (self.node_bits + self.dist_bits + 1) + self.dist_bits])
        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                index_list_edge(Int(0, index_list_edge.width, 10)),
                a(Int(0, a.width, 10)),
                b(Int(0, b.width, 10)),
                cs(Int(0, cs.width, 10)),
                dist_csb(Int(0, dist_csb.width, 10)),
            ).Else(
                thread_index(st1_thread_index),
                thread_valid(st1_thread_valid),
                a(a_t),
                b(b_t),
                cs(cs_t),
                dist_csb(dist_csb_t),
                index_list_edge(Xor(st1_thread_index, st1_edge_index)),
            )
        )

        mem = self.hw_components.create_memory_1r_1w(simulate)
        # Edges_ram
        par = [
            ('width', self.node_bits * 2),
            ('depth', self.th_bits + self.edge_bits),
        ]
        if simulate:
            par.append(('read_f', 1))
            par.append(('init_file', edges_rom_f), )

        con = [
            ('clk', clk),
            ('rd_addr', Cat(st1_thread_index, st1_edge_index)),
            ('out', Cat(a_t, b_t)),
            ('rd', Int(1, 1, 2)),
            ('wr', conf_wr0),
            ('wr_addr', conf_addr0),
            ('wr_data', conf_data0)
        ]
        m.Instance(mem, f'{mem.name}_edges', par, con)

        # Annotations Ram
        par = [
            ('width', (self.node_bits + self.dist_bits + 1) * 3),
            ('depth', self.th_bits + self.edge_bits),
        ]
        if simulate:
            par.append(('read_f', 1))
            par.append(('init_file', annotations_rom_f), )

        con = [
            ('clk', clk),
            ('rd_addr', Cat(st1_thread_index, st1_edge_index)),
            ('out', ann_out),
            ('rd', Int(1, 1, 2)),
            ('wr', conf_wr1),
            ('wr_addr', conf_addr1),
            ('wr_data', conf_data1),
        ]
        m.Instance(mem, f'{mem.name}_annotations', par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage3_yott(self, n2c_rom_f: str, simulate: bool) -> Module:
        name = 'stage3_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        st2_thread_index = m.Input('st2_thread_index', self.th_bits)
        st2_thread_valid = m.Input('st2_thread_valid')
        st2_a = m.Input('st2_a', self.node_bits)
        st2_b = m.Input('st2_b', self.node_bits)
        st2_cs = m.Input('st2_cs', (self.node_bits + 1) * 3)
        st2_dist_csb = m.Input('st2_dist_csb', self.dist_bits * 3)
        st2_index_list_edge = m.Input('st2_index_list_edge', self.distance_table_bits)

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        c_a = m.OutputReg('c_a', self.ij_bits * 2)
        b = m.OutputReg('b', self.node_bits)
        cs_c = m.OutputReg('cs_c', (self.ij_bits * 2 + 1) * 3)
        dist_csb = m.OutputReg('dist_csb', self.dist_bits * 3)
        adj_index = m.OutputReg('adj_index', self.dst_counter_bits)
        index_list_edge = m.OutputReg('index_list_edge', self.distance_table_bits)

        st9_thread_index = m.Input('st9_thread_index', self.th_bits)
        st9_thread_valid = m.Input('st9_thread_valid')
        st9_should_write = m.Input('s9_should_write')
        st9_b = m.Input('st9_b', self.node_bits)
        st9_c_s = m.Input('st9_c_s', self.ij_bits * 2)

        thread_adj_indexes_r = m.Reg('thread_adj_indexes_r', self.dst_counter_bits, self.n_threads)
        c_a_t = m.Wire('c_a_t', self.edge_bits)
        cs_c_t = m.Wire('cs_c_t', (self.ij_bits * 2 + 1) * 3)
        for i in range(3):
            cs_c_t[i * (self.ij_bits * 2 + 1) + (self.ij_bits * 2)].assign(
                st2_cs[i * (self.node_bits + 1) + self.node_bits])

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                c_a(Int(0, c_a.width, 10)),
                b(Int(0, b.width, 10)),
                cs_c(Int(0, cs_c.width, 10)),
                dist_csb(Int(0, dist_csb.width, 10)),
                adj_index(Int(0, adj_index.width, 10)),
                index_list_edge(Int(0, index_list_edge.width, 10))
            ).Else(
                thread_index(st2_thread_index),
                thread_valid(st2_thread_valid),
                b(st2_b),
                c_a(c_a_t),
                cs_c(cs_c_t),
                dist_csb(st2_dist_csb),
                index_list_edge(st2_index_list_edge),
                If(st2_thread_valid)(
                    adj_index(thread_adj_indexes_r[st2_thread_index])
                ).Else(
                    adj_index(Int(0, adj_index.width, 10)),
                ),
                If(AndList(~st9_should_write, st9_thread_valid))(
                    thread_adj_indexes_r[st9_thread_index](
                        thread_adj_indexes_r[st9_thread_index] + Int(1, thread_adj_indexes_r.width, 10))
                )
            )
        )

        # configuration inputs
        conf_wr = m.Input('conf_wr')
        conf_wr_addr = m.Input('conf_wr_addr', self.th_bits + self.node_bits)
        conf_wr_data = m.Input('conf_wr_data', self.ij_bits * 2)

        conf_rd = m.Input('conf_rd')
        conf_rd_addr = m.Input('conf_rd_addr', self.th_bits + self.node_bits)
        conf_rd_data = m.Output('conf_rd_data', self.ij_bits * 2)

        conf_rd_data.assign(c_a_t)

        mem_rd_addr0 = m.Wire('mem_rd_addr0', self.th_bits + self.node_bits)
        mem_rd_addr1 = m.Wire('mem_rd_addr1', self.th_bits + self.node_bits)
        mem_rd_addr2 = m.Wire('mem_rd_addr2', self.th_bits + self.node_bits)
        mem_rd_addr3 = m.Wire('mem_rd_addr3', self.th_bits + self.node_bits)
        mem_wr_addr = m.Wire('mem_wr_addr', self.th_bits + self.node_bits)
        mem_wr = m.Wire('mem_wr')
        mem_wr_data = m.Wire('mem_wr_data', self.ij_bits * 2)

        mem_rd_addr0.assign(Mux(conf_rd, conf_rd_addr, Cat(st2_thread_index, st2_a)))
        mem_rd_addr1.assign(Mux(conf_rd, conf_rd_addr, Cat(st2_thread_index, st2_cs[:self.node_bits])))
        mem_rd_addr2.assign(
            Mux(conf_rd, conf_rd_addr,
                Cat(st2_thread_index, st2_cs[(self.node_bits + 1):(self.node_bits + 1) + self.node_bits])))
        mem_rd_addr3.assign(
            Mux(conf_rd, conf_rd_addr,
                Cat(st2_thread_index, st2_cs[(self.node_bits + 1) * 2:((self.node_bits + 1) * 2) + self.node_bits])))

        mem_wr_addr.assign(Mux(conf_wr, conf_wr_addr, Cat(st9_thread_index, st9_b)))
        mem_wr.assign(Mux(conf_wr, conf_wr, st9_should_write))
        mem_wr_data.assign(Mux(conf_wr, conf_wr_data, st9_c_s))

        n2c_m = self.hw_components.create_memory_2r_1w(simulate)
        par = [
            ('width', self.ij_bits * 2),
            ('depth', self.th_bits + self.node_bits)
        ]
        if simulate:
            par.append(('read_f', 1))
            par.append(('init_file', n2c_rom_f))
            par.append(('write_f', 1))
            par.append(('output_file', n2c_rom_f))

        con = [
            ('clk', clk),
            ('rd_addr0', mem_rd_addr0),
            ('rd_addr1', mem_rd_addr1),
            ('out0', c_a_t),
            ('out1', cs_c_t[:self.ij_bits * 2]),
            ('rd', Int(1, 1, 2)),
            ('wr', mem_wr),
            ('wr_addr', mem_wr_addr),
            ('wr_data', mem_wr_data),
        ]

        m.Instance(n2c_m, f'{n2c_m.name}_0', par, con)

        con = [
            ('clk', clk),
            ('rd_addr0', mem_rd_addr2),
            ('rd_addr1', mem_rd_addr3),
            ('out0', cs_c_t[(self.ij_bits * 2) + 1:(self.ij_bits * 2) * 2 + 1]),
            ('out1', cs_c_t[(self.ij_bits * 2 + 1) * 2:(self.ij_bits * 2 + 1) * 2 + (self.ij_bits * 2)]),
            ('rd', Int(1, 1, 2)),
            ('wr', mem_wr),
            ('wr_addr', mem_wr_addr),
            ('wr_data', mem_wr_data),
        ]

        m.Instance(n2c_m, f'{n2c_m.name}_1', par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage4_yott(self, dst_tbl_rom_f: str, simulate: bool = False):
        name = 'stage4_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        c_a = m.OutputReg('c_a', self.ij_bits * 2)
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        cs_c = m.OutputReg('cs_c', (self.ij_bits * 2 + 1) * 3)
        dist_csb = m.OutputReg('dist_csb', self.dist_bits * 3)

        st3_thread_index = m.Input('st3_thread_index', self.th_bits)
        st3_thread_valid = m.Input('st3_thread_valid')
        st3_c_a = m.Input('st3_c_a', self.ij_bits * 2)
        st3_b = m.Input('st3_b', self.node_bits)
        st3_cs_c = m.Input('st3_cs_c', (self.ij_bits * 2 + 1) * 3)
        st3_dist_csb = m.Input('st3_dist_csb', self.dist_bits * 3)
        st3_adj_index = m.Input('st3_adj_index', self.dst_counter_bits)
        st3_index_list_edge = m.Input('st3_index_list_edge', self.distance_table_bits)

        # configuration inputs
        conf_wr = m.Input('conf_wr')
        conf_addr = m.Input('conf_addr', self.dst_counter_bits - 1 + self.distance_table_bits)
        conf_data = m.Input('conf_data', (self.ij_bits + 1) * 2)

        add_i_t = m.Wire('add_i_t', self.ij_bits + 1)
        add_j_t = m.Wire('add_j_t', self.ij_bits + 1)

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width)),
                thread_valid(Int(0, 1, 10)),
                c_a(Int(0, c_a.width, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                cs_c(Int(0, cs_c.width, 10)),
                dist_csb(Int(0, dist_csb.width, 10)),
            ).Else(
                thread_index(st3_thread_index),
                thread_valid(st3_thread_valid),
                b(st3_b),
                cs_c(st3_cs_c),
                c_a(st3_c_a),
                dist_csb(st3_dist_csb),
                c_s[0:self.ij_bits](st3_c_a[0:self.ij_bits] + add_i_t),
                c_s[self.ij_bits + 2:(self.ij_bits + 2) * 2](st3_c_a[self.ij_bits:self.ij_bits * 2] + add_j_t),

            )
        )

        par = [
            ('width', (self.ij_bits + 1) * 2),
            ('depth', self.dst_counter_bits - 1 + self.distance_table_bits)

        ]

        if simulate:
            par.append(('read_f', 1))
            par.append(('init_file', dst_tbl_rom_f))
        con = [
            ('clk', clk),
            ('rd_addr', Cat(st3_index_list_edge, st3_adj_index[:-1])),
            ('out', Cat(add_i_t, add_j_t)),
            ('rd', Int(1, 1, 2)),
            ('wr', conf_wr),
            ('wr_addr', conf_addr),
            ('wr_data', conf_data),

        ]

        distance_table_m = self.hw_components.create_memory_1r_1w()
        m.Instance(distance_table_m, distance_table_m.name, par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage5_yott(self):
        name = 'stage5_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        cs_c = m.OutputReg('cs_c', (self.ij_bits * 2 + 1) * 3)
        dist_csb = m.OutputReg('dist_csb', self.dist_bits * 3)
        dist_ca_cs = m.OutputReg('dist_ca_cs', self.dist_bits)

        st4_thread_index = m.Input('st4_thread_index', self.th_bits)
        st4_thread_valid = m.Input('st4_thread_valid')
        st4_c_a = m.Input('st4_c_a', self.ij_bits * 2)
        st4_b = m.Input('st4_b', self.node_bits)
        st4_c_s = m.Input('st4_c_s', (self.ij_bits) * 2)
        st4_cs_c = m.Input('st4_cs_c', (self.ij_bits * 2 + 1) * 3)
        st4_dist_csb = m.Input('st4_dist_csb', self.dist_bits * 3)

        d1_t = m.Wire('d1', self.dist_bits)

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                cs_c(Int(0, cs_c.width, 10)),
                dist_csb(Int(0, dist_csb.width, 10)),
                dist_ca_cs(Int(0, dist_ca_cs.width, 10)),
            ).Else(
                thread_index(st4_thread_index),
                thread_valid(st4_thread_valid),
                b(st4_b),
                c_s(st4_c_s),
                cs_c(st4_cs_c),
                dist_csb(st4_dist_csb),
                dist_ca_cs(d1_t)
            )
        )

        dist_m = self.create_manhattan_dist_table()
        par = []
        con = [
            ('source', st4_c_a),
            ('target1', st4_c_s),
            ('d1', d1_t),
        ]
        m.Instance(dist_m, dist_m.name, par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage6_yott(self):
        name = 'stage6_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        cost = m.OutputReg('cost', self.dist_bits + 2)
        dist_ca_cs = m.OutputReg('dist_ca_cs', self.dist_bits)

        st5_thread_index = m.Input('st5_thread_index', self.th_bits)
        st5_thread_valid = m.Input('st5_thread_valid')
        st5_b = m.Input('st5_b', self.node_bits)
        st5_c_s = m.Input('st5_c_s', self.ij_bits * 2)
        st5_cs_c = m.Input('st5_cs_c', (self.ij_bits * 2 + 1) * 3)
        st5_dist_csb = m.Input('st5_dist_csb', self.dist_bits * 3)
        st5_dist_ca_cs = m.Input('st5_dist_ca_cs', self.dist_bits)

        d1_t = m.Wire('d1_t', self.dist_bits)
        d2_t = m.Wire('d2_t', self.dist_bits)
        d3_t = m.Wire('d3_t', self.dist_bits)
        sub1_t = m.Wire('sub1_t', self.dist_bits)
        sub2_t = m.Wire('sub2_t', self.dist_bits)
        sub3_t = m.Wire('sub3_t', self.dist_bits)

        sub1_t.assign(
            Mux(
                st5_cs_c[(self.ij_bits * 2)],
                Int(0, self.dist_bits, 10),
                d1_t - st5_dist_csb[0:self.dist_bits]
            )
        )
        sub2_t.assign(
            Mux(
                st5_cs_c[(self.ij_bits * 2 + 1) + (self.ij_bits * 2)],
                Int(0, self.dist_bits, 10),
                d2_t - st5_dist_csb[self.dist_bits:self.dist_bits * 2]
            )
        )
        sub3_t.assign(
            Mux(
                st5_cs_c[2 * (self.ij_bits * 2 + 1) + (self.ij_bits * 2)],
                Int(0, self.dist_bits, 10),
                d3_t - st5_dist_csb[self.dist_bits * 2:self.dist_bits * 3]
            )
        )

        cost_t = m.Wire('cost_t', self.dist_bits + 2)
        cost_t.assign(sub1_t + sub2_t + sub3_t)

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, thread_valid.width, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                cost(Int(0, cost.width, 10)),
                dist_ca_cs(Int(0, dist_ca_cs.width, 10)),
            ).Else(
                thread_index(st5_thread_index),
                thread_valid(st5_thread_valid),
                b(st5_b),
                c_s(st5_c_s),
                cost(cost_t),
                dist_ca_cs(st5_dist_ca_cs),
            ),
        )

        dist_m = self.create_manhattan_dist_table()
        par = []
        con = [
            ('source', st5_c_s),
            ('target1', st5_cs_c[0:self.ij_bits * 2]),
            ('target2', st5_cs_c[self.ij_bits * 2 + 1:(self.ij_bits * 2 + 1) + (self.ij_bits * 2)]),
            ('target3', st5_cs_c[(self.ij_bits * 2 + 1) * 2: (self.ij_bits * 2 + 1) * 2 + (self.ij_bits * 2)]),
            ('d1', d1_t),
            ('d2', d2_t),
            ('d3', d3_t),
        ]
        m.Instance(dist_m, dist_m.name, par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage7_yott(self, cell_content_f: str, simulate: bool = False):
        name = 'stage7_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        cost = m.OutputReg('cost', self.dist_bits + 2)
        dist_ca_cs = m.OutputReg('dist_ca_cs', self.dist_bits)
        cell_free = m.OutputReg('cell_free')

        st6_thread_index = m.Input('st6_thread_index', self.th_bits)
        st6_thread_valid = m.Input('st6_thread_valid')
        st6_b = m.Input('st6_b', self.node_bits)
        st6_c_s = m.Input('st6_c_s', self.ij_bits * 2)
        st6_cost = m.Input('st6_cost', self.dist_bits + 2)
        st6_dist_ca_cs = m.Input('st6_dist_ca_cs', self.dist_bits)

        st9_thread_index = m.Input('st9_thread_index', self.th_bits)
        st9_should_write = m.Input('s9_should_write')
        st9_c_s = m.Input('st9_c_s', self.ij_bits * 2)

        conf_wr = m.Input('conf_wr')
        conf_addr = m.Input('conf_addr', self.th_bits + self.ij_bits * 2)
        conf_data = m.Input('conf_data')

        cell_free_t = m.Wire('cell_free_t')
        content_t = m.Wire('content_t')
        out_of_border_t = m.Wire('out_of_border_t')
        out_of_border_t.assign(OrList(
            st6_c_s[0:self.ij_bits] > Int(self.n_lines - 1, self.ij_bits + 1, 10),
            st6_c_s[self.ij_bits:self.ij_bits * 2] > Int(self.n_lines - 1, self.ij_bits + 1, 10)
        ))
        cell_free_t.assign(Uand(Cat(~content_t, ~out_of_border_t, st6_thread_valid)))

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                cost(Int(0, cost.width, 10)),
                dist_ca_cs(Int(0, dist_ca_cs.width, 10)),
                cell_free(Int(0, 1, 10)),
            ).Else(
                thread_index(st6_thread_index),
                thread_valid(st6_thread_valid),
                b(st6_b),
                c_s(st6_c_s),
                cost(st6_cost),
                dist_ca_cs(st6_dist_ca_cs),
                cell_free(cell_free_t),
            ),
        )

        mem_wr = m.Wire('mem_wr')
        mem_addr = m.Wire('mem_addr', self.th_bits + self.ij_bits * 2)
        mem_data = m.Wire('mem_data')

        mem_wr.assign(Mux(conf_wr, conf_wr, st9_should_write))
        mem_addr.assign(Mux(conf_wr, conf_addr, Cat(st9_thread_index, st9_c_s)))
        mem_data.assign(Mux(conf_wr, conf_data, Int(1, 1, 10)))

        par = [
            ('width', 1),
            ('depth', self.th_bits + self.ij_bits * 2),
        ]
        if simulate:
            par.append(('read_f', 1))
            par.append(('init_file', cell_content_f))
        con = [
            ('clk', clk),
            ('rd_addr', Cat(st6_thread_index, st6_c_s)),
            ('out', content_t),
            ('rd', Int(1, 1, 2)),
            ('wr', mem_wr),
            ('wr_addr', mem_addr),
            ('wr_data', mem_data),
        ]

        cells_m = self.hw_components.create_memory_1r_1w()
        m.Instance(cells_m, cells_m.name, par, con)

        HwUtil.initialize_regs(m)
        return m

    def create_stage8_yott(self):
        name = 'stage8_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        cost = m.OutputReg('cost', self.dist_bits + 2)
        dist_ca_cs = m.OutputReg('dist_ca_cs', self.dist_bits)
        save_cell = m.OutputReg('save_cell')
        should_write = m.OutputReg('should_write')

        st7_thread_index = m.Input('st7_thread_index', self.th_bits)
        st7_thread_valid = m.Input('st7_thread_valid')
        st7_b = m.Input('st7_b', self.node_bits)
        st7_c_s = m.Input('st7_c_s', self.ij_bits * 2)
        st7_cost = m.Input('st7_cost', self.dist_bits + 2)
        st7_dist_ca_cs = m.Input('st7_dist_ca_cs', self.dist_bits)
        st7_cell_free = m.Input('st7_cell_free')

        save_cell_t = m.Wire('save_cell_t')
        should_write_t = m.Wire('should_write_t')

        should_write_t.assign(
            AndList(st7_cell_free, OrList(AndList(st7_dist_ca_cs < 3, st7_cost == 0), st7_dist_ca_cs >= 3)))
        save_cell_t.assign(AndList(st7_cell_free, st7_dist_ca_cs < 3, ~should_write_t))

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                cost(Int(0, cost.width, 10)),
                dist_ca_cs(Int(0, dist_ca_cs.width, 10)),
                save_cell(Int(0, 1, 10)),
                should_write(Int(0, 1, 10)),
            ).Else(
                thread_index(st7_thread_index),
                thread_valid(st7_thread_valid),
                b(st7_b),
                c_s(st7_c_s),
                cost(st7_cost),
                dist_ca_cs(st7_dist_ca_cs),
                save_cell(save_cell_t),
                should_write(should_write_t),
            ),
        )

        HwUtil.initialize_regs(m)
        return m

    def create_stage9_yott(self):
        name = 'stage9_yott'
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')

        thread_index = m.OutputReg('thread_index', self.th_bits)
        thread_valid = m.OutputReg('thread_valid')
        b = m.OutputReg('b', self.node_bits)
        c_s = m.OutputReg('c_s', self.ij_bits * 2)
        should_write = m.OutputReg('should_write')
        write_enable = m.OutputReg('write_enable')
        input_data = m.OutputReg('input_data', self.fifo_width)

        st8_thread_index = m.Input('st8_thread_index', self.th_bits)
        st8_thread_valid = m.Input('st8_thread_valid')
        st8_b = m.Input('st8_b', self.node_bits)
        st8_c_s = m.Input('st8_c_s', self.ij_bits * 2)
        st8_cost = m.Input('st8_cost', self.dist_bits + 2)
        st8_dist_ca_cs = m.Input('st8_dist_ca_cs', self.dist_bits)
        st8_save_cell = m.Input('st8_save_cell')
        st8_should_write = m.Input('st8_should_write')

        threads_current_adj_dists = m.Reg('threads_current_adj_dists', self.dist_bits, self.n_threads)
        threads_free_cell_valid = m.Reg('threads_free_cell_valid', self.n_threads)
        threads_free_cell0 = m.Reg('threads_free_cell0', self.ij_bits * 2)
        threads_free_cell1 = m.Reg('threads_free_cell1', self.dist_bits)

        was_there_change = m.Wire('was_there_change')
        was_there_change.assign(st8_dist_ca_cs != threads_current_adj_dists[st8_thread_index])

        should = m.Wire('should')
        should.assign(AndList(st8_should_write, st8_thread_valid))

        m.Always(Posedge(clk))(
            If(rst)(
                thread_index(Int(0, thread_index.width, 10)),
                thread_valid(Int(0, 1, 10)),
                b(Int(0, b.width, 10)),
                c_s(Int(0, c_s.width, 10)),
                should_write(Int(0, should_write.width, 10)),
                write_enable(Int(0, 1, 10)),
                input_data(Int(0, input_data.width, 10)),
                threads_free_cell_valid(Int(pow(2, self.n_threads) - 1, threads_free_cell_valid.width, 2))
            ).Else(
                write_enable(st8_thread_valid),
                input_data(Cat(st8_thread_index, should)),
                thread_index(st8_thread_index),
                thread_valid(st8_thread_valid),
                b(st8_b),
                c_s(st8_c_s),
                should_write(should),
                If(should)(
                    threads_current_adj_dists[st8_thread_index](Int(1, self.dist_bits, 10)),
                    threads_free_cell1[st8_thread_index](Int(pow(2, self.dist_bits) - 1, self.dist_bits, 2)),
                    threads_free_cell_valid[st8_thread_index](Int(0, 1, 10)),
                ),
                If(~st8_thread_valid)(
                    threads_current_adj_dists[st8_thread_index](1),
                    threads_free_cell0[st8_thread_index](Int(0, threads_free_cell0.width, 10)),
                    threads_free_cell1[st8_thread_index](Int(pow(2, self.dist_bits) - 1, self.dist_bits, 2)),
                ).Else(
                    If(AndList(st8_save_cell, st8_cost < threads_free_cell1[st8_thread_index]))(
                        threads_free_cell0[st8_thread_index](c_s),
                        threads_free_cell1[st8_thread_index](st8_cost),
                        threads_free_cell_valid[st8_thread_index](Int(1, 1, 10)),
                    ),
                    If(was_there_change)(
                        threads_current_adj_dists[st8_thread_index](st8_dist_ca_cs),
                        If(threads_free_cell_valid[st8_thread_index])(
                            c_s(threads_free_cell0[st8_thread_index])
                        )
                    ),

                ),

            )
        )

        HwUtil.initialize_regs(m)
        return m

    def create_acc(self, copies: int = 1):
        acc_num_in = copies
        acc_num_out = copies

        copies = copies
        bus_width = 128
        acc_data_in_width = bus_width
        acc_data_out_width = bus_width
        bus_data_width = acc_data_in_width

        name = "yott_acc"
        m = Module(name)

        clk = m.Input('clk')
        rst = m.Input('rst')
        start = m.Input('start')

        acc_user_done_rd_data = m.Input('acc_user_done_rd_data', acc_num_in)
        acc_user_done_wr_data = m.Input('acc_user_done_wr_data', acc_num_out)

        acc_user_request_read = m.Output('acc_user_request_read', acc_num_in)
        acc_user_read_data_valid = m.Input('acc_user_read_data_valid', acc_num_in)
        acc_user_read_data = m.Input('acc_user_read_data', bus_data_width * acc_num_in)

        acc_user_available_write = m.Input('acc_user_available_write', acc_num_out)
        acc_user_request_write = m.Output('acc_user_request_write', acc_num_out)
        acc_user_write_data = m.Output('acc_user_write_data', bus_data_width * acc_num_out)

        acc_user_done = m.Output('acc_user_done')

        start_reg = m.Reg('start_reg')
        yott_interface_done = m.Wire('yott_interface_done', acc_num_in)

        acc_user_done.assign(Uand(yott_interface_done))

        m.Always(Posedge(clk))(
            If(rst)(
                start_reg(0)
            ).Else(
                start_reg(Or(start_reg, start))
            )
        )

        yott_interface = self.create_yott_interface()
        for i in range(copies):
            par = []
            con = [
                ('clk', clk),
                ('rst', rst),
                ('start', start_reg),
                ('yott_done_rd_data', acc_user_done_rd_data[i]),
                ('yott_done_wr_data', acc_user_done_wr_data[i]),
                ('yott_request_read', acc_user_request_read[i]),
                ('yott_read_data_valid', acc_user_read_data_valid[i]),
                ('yott_read_data', acc_user_read_data[i * acc_data_in_width:(i + 1) * acc_data_in_width]),
                ('yott_available_write', acc_user_available_write[i]),
                ('yott_request_write', acc_user_request_write[i]),
                ('yott_write_data', acc_user_write_data[i * acc_data_out_width:(i + 1) * acc_data_out_width]),
                ('yott_interface_done', yott_interface_done[i])]
            m.EmbeddedCode("(* keep_hierarchy = \"yes\" *)")
            m.Instance(yott_interface, f'{yott_interface.name}_{i}', par, con)

            HwUtil.initialize_regs(m)

        return m

    def create_yott_interface(self):
        # self.copies = copies
        bus_width = 128
        pipe_width = 64

        name = "yott_interface"
        m = Module(name)

        # interface I/O interface - Begin ------------------------------------------------------------------------------
        clk = m.Input('clk')
        rst = m.Input('rst')
        start = m.Input('start')

        yott_done_rd_data = m.Input('yott_done_rd_data')
        yott_done_wr_data = m.Input('yott_done_wr_data')

        yott_request_read = m.Output('yott_request_read')
        yott_read_data_valid = m.Input('yott_read_data_valid')
        yott_read_data = m.Input('yott_read_data', bus_width)

        yott_available_write = m.Input('yott_available_write')
        yott_request_write = m.OutputReg('yott_request_write')
        yott_write_data = m.OutputReg('yott_write_data', bus_width)

        yott_interface_done = m.Output('yott_interface_done')
        # interface I/O interface - End --------------------------------------------------------------------------------

        yott_interface_done.assign(Uand(Cat(yott_done_wr_data, yott_done_rd_data)))

        start_pipe = m.Reg('start_pipe')

        pop_data = m.Reg('pop_data')
        available_pop = m.Wire('available_pop')
        data_out = m.Wire('data_out', pipe_width)
        visited_edges = m.Reg('visited_edges', self.edge_bits)
        total_pipeline_counter = m.Wire('total_pipeline_counter', 32)

        fsm_sd = m.Reg('fms_sd', 5)

        fsm_sd_edges_idle = m.Localparam('fsm_sd_edges_idle', 0, fsm_sd.width)
        fsm_sd_edges_send_data = m.Localparam('fsm_sd_edges_send_data', 1, fsm_sd.width)
        fsm_sd_edges_verify = m.Localparam('fsm_sd_edges_verify', 2, fsm_sd.width)

        fsm_sd_annotations_idle = m.Localparam('fsm_sd_annotations_idle', 3, fsm_sd.width)
        fsm_sd_annotations_send_data = m.Localparam('fsm_sd_annotations_send_data', 4, fsm_sd.width)
        fsm_sd_annotations_verify = m.Localparam('fsm_sd_annotations_verify', 5, fsm_sd.width)

        fsm_sd_n2c_idle = m.Localparam('fsm_sd_n2c_idle', 6, fsm_sd.width)
        fsm_sd_n2c_send_data = m.Localparam('fsm_sd_n2c_send_data', 7, fsm_sd.width)
        fsm_sd_n2c_verify = m.Localparam('fsm_sd_n2c_verify', 8, fsm_sd.width)

        fsm_sd_dist_idle = m.Localparam('fsm_sd_dist_idle', 9, fsm_sd.width)
        fsm_sd_dist_send_data = m.Localparam('fsm_sd_dist_send_data', 10, fsm_sd.width)
        fsm_sd_dist_verify = m.Localparam('fsm_sd_dist_verify', 11, fsm_sd.width)

        fsm_sd_c_idle = m.Localparam('fsm_sd_c_idle', 12, fsm_sd.width)
        fsm_sd_c_send_data = m.Localparam('fsm_sd_c_send_data', 13, fsm_sd.width)
        fsm_sd_c_verify = m.Localparam('fsm_sd_c_verify', 14, fsm_sd.width)

        fsm_sd_vedges_idle = m.Localparam('fsm_sd_vedges_idle', 15, fsm_sd.width)
        fsm_sd_vedges_send_data = m.Localparam('fsm_sd_vedges_send_data', 16, fsm_sd.width)
        fsm_sd_done = m.Localparam('fsm_sd_done', 17, fsm_sd.width)

        # read data back
        yott_done = m.Wire('yott_done')
        st3_conf_rd = m.Reg('st3_conf_rd')
        st3_conf_rd_addr = m.Reg('st3_conf_rd_addr', self.th_bits + self.node_bits)
        st3_conf_rd_data = m.Wire('st3_conf_rd_data', self.ij_bits * 2)

        # configurations
        st2_conf_wr0 = m.Reg('st2_conf_wr0')
        st2_conf_addr0 = m.Reg('st2_conf_addr0', self.edge_bits + self.th_bits)
        st2_conf_data0 = m.Reg('st2_conf_data0', self.node_bits * 2)
        st2_conf_wr1 = m.Reg('st2_conf_wr1')
        st2_conf_addr1 = m.Reg('st2_conf_addr1', self.th_bits + self.edge_bits)
        st2_conf_data1 = m.Reg('st2_conf_data1', (self.node_bits + self.dist_bits + 1) * 3)

        st3_conf_wr = m.Reg('st3_conf_wr')
        st3_conf_wr_addr = m.Reg('st3_conf_wr_addr', self.th_bits + self.node_bits)
        st3_conf_wr_data = m.Reg('st3_conf_wr_data', self.ij_bits * 2)

        st4_conf_wr = m.Reg('st4_conf_wr')
        st4_conf_addr = m.Reg('st4_conf_addr', self.dst_counter_bits - 1 + self.distance_table_bits)
        st4_conf_data = m.Reg('st4_conf_data', (self.ij_bits + 1) * 2)

        st7_conf_wr = m.Reg('st7_conf_wr')
        st7_conf_addr = m.Reg('st7_conf_addr', self.th_bits + self.ij_bits * 2)
        st7_conf_data = m.Reg('st7_conf_data')

        # fixme rst
        m.Always(Posedge(clk))(
            If(rst)(
                st2_conf_wr0(0),
                st2_conf_addr0(0),
                st2_conf_data0(0),
                st2_conf_wr1(0),
                st2_conf_addr1(0),
                st2_conf_data1(0),
                st3_conf_wr(0),
                st3_conf_wr_addr(0),
                st3_conf_wr_data(0),
                st4_conf_wr(0),
                st4_conf_addr(0),
                st4_conf_data(0),
                st7_conf_wr(0),
                st7_conf_addr(0),
                st7_conf_data(0),
                pop_data(0),
                start_pipe(0),
                fsm_sd(fsm_sd_edges_idle),
            ).Elif(start)(
                st2_conf_wr0(0),
                st2_conf_wr1(0),
                st3_conf_wr(0),
                st4_conf_wr(0),
                st7_conf_wr(0),
                start_pipe(0),
                pop_data(0),
                Case(fsm_sd)(
                    When(fsm_sd_edges_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_edges_send_data)
                        )
                    ),
                    When(fsm_sd_edges_send_data)(
                        st2_conf_wr0(1),
                        st2_conf_data0(data_out[:st2_conf_data0.width]),
                        fsm_sd(fsm_sd_edges_verify)
                    ),
                    When(fsm_sd_edges_verify)(
                        If(Uand(st2_conf_addr0))(
                            fsm_sd(fsm_sd_annotations_idle)
                        ).Else(
                            st2_conf_addr0.inc(),
                            fsm_sd(fsm_sd_edges_idle)
                        ),
                    ),
                    When(fsm_sd_annotations_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_annotations_send_data)
                        )
                    ),
                    When(fsm_sd_annotations_send_data)(
                        st2_conf_wr1(1),
                        st2_conf_data1(data_out[:st2_conf_data1.width]),
                        fsm_sd(fsm_sd_annotations_verify)
                    ),
                    When(fsm_sd_annotations_verify)(
                        If(Uand(st2_conf_addr1))(
                            fsm_sd(fsm_sd_n2c_idle)
                        ).Else(
                            st2_conf_addr1.inc(),
                            fsm_sd(fsm_sd_annotations_idle)
                        ),
                    ),
                    When(fsm_sd_n2c_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_n2c_send_data)
                        )
                    ),
                    When(fsm_sd_n2c_send_data)(
                        st3_conf_wr(1),
                        st3_conf_wr_data(data_out[:st3_conf_wr_data.width]),
                        fsm_sd(fsm_sd_n2c_verify)
                    ),
                    When(fsm_sd_n2c_verify)(
                        If(Uand(st3_conf_wr_addr))(
                            fsm_sd(fsm_sd_dist_idle)
                        ).Else(
                            st3_conf_wr_addr.inc(),
                            fsm_sd(fsm_sd_n2c_idle)
                        ),
                    ),
                    When(fsm_sd_dist_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_dist_send_data)
                        )
                    ),
                    When(fsm_sd_dist_send_data)(
                        st4_conf_wr(1),
                        st4_conf_data(data_out[:st4_conf_data.width]),
                        fsm_sd(fsm_sd_dist_verify)
                    ),
                    When(fsm_sd_dist_verify)(
                        If(Uand(st4_conf_addr))(
                            fsm_sd(fsm_sd_c_idle)
                        ).Else(
                            st4_conf_addr.inc(),
                            fsm_sd(fsm_sd_dist_idle)
                        ),
                    ),
                    When(fsm_sd_c_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_c_send_data)
                        )
                    ),
                    When(fsm_sd_c_send_data)(
                        st7_conf_wr(1),
                        st7_conf_data(data_out[:st7_conf_data.width]),
                        fsm_sd(fsm_sd_c_verify)
                    ),
                    When(fsm_sd_c_verify)(
                        If(Uand(st7_conf_addr))(
                            fsm_sd(fsm_sd_vedges_idle)
                        ).Else(
                            st7_conf_addr.inc(),
                            fsm_sd(fsm_sd_c_idle)
                        ),
                    ),
                    When(fsm_sd_vedges_idle)(
                        If(available_pop)(
                            pop_data(1),
                            fsm_sd(fsm_sd_vedges_send_data)
                        )
                    ),
                    When(fsm_sd_vedges_send_data)(
                        visited_edges(data_out[:visited_edges.width]),
                        fsm_sd(fsm_sd_done)
                    ),
                    When(fsm_sd_done)(
                        start_pipe(1)
                    )
                )
            )
        )

        # Data Consumer - Begin ----------------------------------------------------------------------------------------
        m.EmbeddedCode('\n//Data Consumer - Begin')
        fsm_consume = m.Reg('fsm_consume', 2)
        fsm_consume_wait = m.Localparam('fsm_consume_wait', 0)
        fsm_consume_consume = m.Localparam('fsm_consume_consume', 1)
        fsm_consume_verify = m.Localparam('fsm_consume_verify', 2)
        fsm_consume_done = m.Localparam('fsm_consume_done', 3)

        m.Always(Posedge(clk))(
            If(rst)(
                st3_conf_rd(0),
                st3_conf_rd_addr(0),
                yott_request_write(0),
                fsm_consume(fsm_consume_wait)
            ).Else(
                st3_conf_rd(0),
                yott_request_write(0),
                Case(fsm_consume)(
                    When(fsm_consume_wait)(
                        If(yott_available_write)(
                            If(yott_done)(
                                st3_conf_rd(1),
                                fsm_consume(fsm_consume_consume),
                            ),
                        ),

                    ),
                    When(fsm_consume_consume)(
                        yott_request_write(1),
                        yott_write_data(Cat(Int(0, bus_width - st3_conf_rd_data.width, 10), st3_conf_rd_data)),
                        st3_conf_rd_addr.inc(),
                        fsm_consume(fsm_consume_verify)
                    ),
                    When(fsm_consume_verify)(
                        If(st3_conf_rd_addr == pow(2, self.th_bits + self.node_bits))(
                            fsm_consume(fsm_consume_done)
                        ).Else(
                            fsm_consume(fsm_consume_wait)
                        )
                    ),
                    When(fsm_consume_done)(

                    ),
                )
            )
        )
        m.EmbeddedCode('//Data Consumer - Begin')
        # Data Consumer - End ------------------------------------------------------------------------------------------

        fetch_data = self.hw_components.create_fetch_data(bus_width, pipe_width)
        par = []
        con = [
            ('clk', clk),
            ('rst', rst),
            ('start', start),
            ('request_read', yott_request_read),
            ('data_valid', yott_read_data_valid),
            ('read_data', yott_read_data),
            ('pop_data', pop_data),
            ('available_pop', available_pop),
            ('data_out', data_out)
        ]
        m.EmbeddedCode("(* keep_hierarchy = \"yes\" *)")
        m.Instance(fetch_data, fetch_data.name, par, con)

        par = []
        con = [
            ('clk', clk),
            ('rst', rst),
            ('start', start_pipe),
            ('visited_edges', visited_edges),
            ('done', yott_done),
            ('st2_conf_wr0', st2_conf_wr0),
            ('st2_conf_addr0', st2_conf_addr0),
            ('st2_conf_data0', st2_conf_data0),
            ('st2_conf_wr1', st2_conf_wr1),
            ('st2_conf_addr1', st2_conf_addr1),
            ('st2_conf_data1', st2_conf_data1),
            ('st3_conf_wr', st3_conf_wr),
            ('st3_conf_wr_addr', st3_conf_wr_addr),
            ('st3_conf_wr_data', st3_conf_wr_data),
            ('st3_conf_rd', st3_conf_rd),
            ('st3_conf_rd_addr', st3_conf_rd_addr),
            ('st3_conf_rd_data', st3_conf_rd_data),
            ('st4_conf_wr', st4_conf_wr),
            ('st4_conf_addr', st4_conf_addr),
            ('st4_conf_data', st4_conf_data),
            ('st7_conf_wr', st7_conf_wr),
            ('st7_conf_addr', st7_conf_addr),
            ('st7_conf_data', st7_conf_data),
        ]
        aux = self.create_yott_pipeline_hw('', '', '', '', '', False)
        m.Instance(aux, aux.name, par, con)

        HwUtil.initialize_regs(m)

        return m
