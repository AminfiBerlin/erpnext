# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
import webnotes
from webnotes.utils import cstr, flt
from webnotes.model.doc import addchild
from webnotes.model.wrapper import getlist
from webnotes.model.code import get_obj
from webnotes import msgprint

sql = webnotes.conn.sql

class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist
		self.item_dict = {}

	def get_so_details(self, so):
		"""Pull other details from so"""
		so = sql("""select transaction_date, customer, grand_total 
			from `tabSales Order` where name = %s""", so, as_dict = 1)
		ret = {
			'sales_order_date': so and so[0]['transaction_date'] or '',
			'customer' : so[0]['customer'] or '',
			'grand_total': so[0]['grand_total']
		}
		return ret	
			
	def get_item_details(self, item_code):
		""" Pull other item details from item master"""

		item = sql("""select description, stock_uom, default_bom 
			from `tabItem` where name = %s""", item_code, as_dict =1)
		ret = {
			'description'	: item and item[0]['description'],
			'stock_uom'		: item and item[0]['stock_uom'],
			'bom_no'		: item and item[0]['default_bom']
		}
		return ret

	def clear_so_table(self):
		self.doclist = self.doc.clear_table(self.doclist, 'pp_so_details')

	def clear_item_table(self):
		self.doclist = self.doc.clear_table(self.doclist, 'pp_details')
		
	def validate_company(self):
		if not self.doc.company:
			msgprint("Please enter Company", raise_exception=1)

	def get_open_sales_orders(self):
		""" Pull sales orders  which are pending to deliver based on criteria selected"""
		so_filter = item_filter = ""
		if self.doc.from_date:
			so_filter += ' and so.transaction_date >= "' + self.doc.from_date + '"'
		if self.doc.to_date:
			so_filter += ' and so.transaction_date <= "' + self.doc.to_date + '"'
		if self.doc.customer:
			so_filter += ' and so.customer = "' + self.doc.customer + '"'
			
		if self.doc.fg_item:
			item_filter += ' and item.name = "' + self.doc.fg_item + '"'
		
		open_so = sql("""
			select distinct so.name, so.transaction_date, so.customer, so.grand_total
			from `tabSales Order` so, `tabSales Order Item` so_item
			where so_item.parent = so.name
				and so.docstatus = 1 and so.status != "Stopped"
				and so.company = %s
				and ifnull(so_item.qty, 0) > ifnull(so_item.delivered_qty, 0) %s
				and (exists (select * from `tabItem` item where item.name=so_item.item_code
					and (ifnull(item.is_pro_applicable, 'No') = 'Yes' 
						or ifnull(item.is_sub_contracted_item, 'No') = 'Yes') %s)
					or exists (select * from `tabDelivery Note Packing Item` dnpi
						where dnpi.parent = so.name and dnpi.parent_item = so_item.item_code
							and exists (select * from `tabItem` item where item.name=dnpi.item_code
								and (ifnull(item.is_pro_applicable, 'No') = 'Yes' 
									or ifnull(item.is_sub_contracted_item, 'No') = 'Yes') %s)))
			""" % ('%s', so_filter, item_filter, item_filter), self.doc.company, as_dict=1)
		
		self.add_so_in_table(open_so)

	def add_so_in_table(self, open_so):
		""" Add sales orders in the table"""
		so_list = [d.sales_order for d in getlist(self.doclist, 'pp_so_details')]
		for r in open_so:
			if cstr(r['name']) not in so_list:
				pp_so = addchild(self.doc, 'pp_so_details', 
					'Production Plan Sales Order', 1, self.doclist)
				pp_so.sales_order = r['name']
				pp_so.sales_order_date = cstr(r['transaction_date'])
				pp_so.customer = cstr(r['customer'])
				pp_so.grand_total = flt(r['grand_total'])

	def get_items_from_so(self):
		""" Pull items from Sales Order, only proction item
			and subcontracted item will be pulled from Packing item 
			and add items in the table
		"""
		items = self.get_items()
		self.add_items(items)

	def get_items(self):
		so_list = filter(None, [d.sales_order for d in getlist(self.doclist, 'pp_so_details')])
		if not so_list:
			msgprint("Please enter sales order in the above table", raise_exception=1)
			
		items = sql("""select distinct parent, item_code,
			(qty - ifnull(delivered_qty, 0)) as pending_qty
			from `tabSales Order Item` so_item
			where parent in (%s) and docstatus = 1 and ifnull(qty, 0) > ifnull(delivered_qty, 0)
			and exists (select * from `tabItem` item where item.name=so_item.item_code
				and (ifnull(item.is_pro_applicable, 'No') = 'Yes' 
					or ifnull(item.is_sub_contracted_item, 'No') = 'Yes'))""" % \
			(", ".join(["%s"] * len(so_list))), tuple(so_list), as_dict=1)
		
		dnpi_items = sql("""select distinct dnpi.parent, dnpi.item_code,
			(((so_item.qty - ifnull(so_item.delivered_qty, 0)) * dnpi.qty) / so_item.qty) 
				as pending_qty
			from `tabSales Order Item` so_item, `tabDelivery Note Packing Item` dnpi
			where so_item.parent = dnpi.parent and so_item.docstatus = 1 
			and dnpi.parent_item = so_item.item_code
			and so_item.parent in (%s) and ifnull(so_item.qty, 0) > ifnull(so_item.delivered_qty, 0)
			and exists (select * from `tabItem` item where item.name=dnpi.item_code
				and (ifnull(item.is_pro_applicable, 'No') = 'Yes' 
					or ifnull(item.is_sub_contracted_item, 'No') = 'Yes'))""" % \
			(", ".join(["%s"] * len(so_list))), tuple(so_list), as_dict=1)

		return items + dnpi_items
		

	def add_items(self, items):
		self.clear_item_table()

		for p in items:
			item_details = sql("""select description, stock_uom, default_bom 
				from tabItem where name=%s""", p['item_code'])
			pi = addchild(self.doc, 'pp_details', 'Production Plan Item', 1, self.doclist)
			pi.sales_order				= p['parent']
			pi.item_code				= p['item_code']
			pi.description				= item_details and item_details[0][0] or ''
			pi.stock_uom				= item_details and item_details[0][1] or ''
			pi.bom_no					= item_details and item_details[0][2] or ''
			pi.so_pending_qty			= flt(p['pending_qty'])
			pi.planned_qty				= flt(p['pending_qty'])
	

	def validate_data(self):
		for d in getlist(self.doclist, 'pp_details'):
			self.validate_bom_no(d)
			if not flt(d.planned_qty):
				msgprint("Please Enter Planned Qty for item: %s at row no: %s" %
					(d.item_code, d.idx), raise_exception=1)
				
	def validate_bom_no(self, d):
		if not d.bom_no:
			msgprint("Please enter bom no for item: %s at row no: %s" % 
				(d.item_code, d.idx), raise_exception=1)
		else:
			bom = sql("""select name from `tabBOM` where name = %s and item = %s 
				and docstatus = 1 and ifnull(is_active, 'No') = 'Yes'""", 
				(d.bom_no, d.item_code), as_dict = 1)
			if not bom:
				msgprint("""Incorrect BOM No: %s entered for item: %s at row no: %s
					May be BOM is inactive or for other item or does not exists in the system""" % 
					(d.bom_no, d.item_doce, d.idx), raise_exception=1)

	def raise_production_order(self):
		"""It will raise production order (Draft) for all distinct FG items"""
		self.validate_company()
		self.validate_data()

		items = self.get_distinct_items_and_boms()[1]
		pro = get_obj('Production Control').create_production_order(items)
		if pro:
			msgprint("Following Production Order has been generated:\n" + '\n'.join(pro))
		else :
			msgprint("No Production Order generated.")


	def get_distinct_items_and_boms(self):
		""" Club similar BOM and item for processing"""
		item_dict, bom_dict = {}, {}
		for d in self.doclist.get({"parentfield": "pp_details"}):
			bom_dict[d.bom_no] = bom_dict.get(d.bom_no, 0) + flt(d.planned_qty)
			item_dict[(d.item_code, d.sales_order)] = {
				"qty" : flt(item_dict.get((d.item_code, d.sales_order), {}).get("qty")) + \
				 	flt(d.planned_qty),
				"bom_no": d.bom_no,
				"description": d.description,
				"stock_uom": d.stock_uom,
				"use_multi_level_bom": self.doc.use_multi_level_bom,
				"company": self.doc.company,
			}
		return bom_dict, item_dict

	def download_raw_materials(self):
		""" Create csv data for required raw material to produce finished goods"""
		bom_dict = self.get_distinct_items_and_boms()[0]
		self.get_raw_materials(bom_dict)
		return self.get_csv()

	def get_raw_materials(self, bom_dict):
		""" Get raw materials considering sub-assembly items """
		for bom in bom_dict:
			if self.doc.use_multi_level_bom:
				# get all raw materials with sub assembly childs					
				fl_bom_items = sql("""
					select 
						item_code,ifnull(sum(qty_consumed_per_unit),0)*%s as qty, 
						description, stock_uom
					from 
						( 
							select distinct fb.name, fb.description, fb.item_code,
							 	fb.qty_consumed_per_unit, fb.stock_uom 
							from `tabBOM Explosion Item` fb,`tabItem` it 
							where it.name = fb.item_code 
							and ifnull(it.is_pro_applicable, 'No') = 'No'
							and ifnull(it.is_sub_contracted_item, 'No') = 'No' 
							and fb.docstatus<2 and fb.parent=%s
						) a
					group by item_code,stock_uom
				""" , (flt(bom_dict[bom]), bom))
			else:
				# Get all raw materials considering SA items as raw materials, 
				# so no childs of SA items
				fl_bom_items = sql("""
					select item_code, ifnull(sum(qty_consumed_per_unit), 0) * '%s', 
						description, stock_uom 
					from `tabBOM Item` 
					where parent = '%s' and docstatus < 2 
					group by item_code
				""" % (flt(bom_dict[bom]), bom))

			self.make_items_dict(fl_bom_items)

	def make_items_dict(self, item_list):
		for i in item_list:
			self.item_dict[i[0]] = [(flt(self.item_dict.get(i[0], [0])[0]) + flt(i[1])), i[2], i[3]]


	def get_csv(self):
		item_list = [['Item Code', 'Description', 'Stock UOM', 'Required Qty', 'Warehouse',
		 	'Quantity Requested for Purchase', 'Ordered Qty', 'Actual Qty']]
		for d in self.item_dict:
			item_list.append([d, self.item_dict[d][1], self.item_dict[d][2], self.item_dict[d][0]])
			item_qty= sql("""select warehouse, indented_qty, ordered_qty, actual_qty 
				from `tabBin` where item_code = %s""", d)
			i_qty, o_qty, a_qty = 0, 0, 0
			for w in item_qty:
				i_qty, o_qty, a_qty = i_qty + flt(w[1]), o_qty + flt(w[2]), a_qty + flt(w[3])
				item_list.append(['', '', '', '', w[0], flt(w[1]), flt(w[2]), flt(w[3])])
			if item_qty:
				item_list.append(['', '', '', '', 'Total', i_qty, o_qty, a_qty])

		return item_list