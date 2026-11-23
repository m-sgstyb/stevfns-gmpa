#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import cvxpy as cp


class __Edge:
    """Basic Directed Edge Class"""
    def __init__(self):
        self.source_node = False
        self.target_node = False
        return
    
    def attach_source_node(self, source_node):
        self.source_node = source_node
        if source_node == False:
            return
        if self in source_node.output_edges:
            return
        source_node.attach_output_edge(self)
        return
    
    def attach_target_node(self, target_node):
        self.target_node = target_node
        if target_node == False:
            return
        if self in target_node.input_edges:
            return
        target_node.attach_input_edge(self)
        return


class Edge_STEVFNs(__Edge):
    """STEVFNs Edge Class"""
    conversion_fun = staticmethod(lambda flow,params:flow)
    def __init__(self):
        super().__init__()
        self.flow = cp.Constant(0)
        self.conversion_fun_params = dict()
        return
    
    def extract_flow(self):
        return self.conversion_fun(self.flow, self.conversion_fun_params)