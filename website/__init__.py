from __future__ import unicode_literals
install_docs = [
	{"doctype":"Role", "role_name":"Blogger", "name":"Blogger"},
	{"doctype":"Role", "role_name":"Website Manager", "name":"Website Manager"},
]

import webnotes

@webnotes.whitelist(allow_guest=True)
def send_message():
	from webnotes.model.doc import Document
	args = webnotes.form_dict
	
	d = Document('Support Ticket')
	d.subject = webnotes.form_dict.get('subject', 'Website Query')
	d.description = webnotes.form_dict.get('message')
	d.raised_by = webnotes.form_dict.get('sender')
	
	if not d.description:
		webnotes.msgprint('Please write something', raise_exception=True)
		
	if not d.raised_by:
		webnotes.msgprint('Please give us your email id so that we can write back to you', raise_exception=True)
	
	# make lead or contact
	
	d.save()
	webnotes.msgprint('Thank you!')
	
def get_site_address():
	from webnotes.utils import get_request_site_address
	url = get_request_site_address()

	if not url or url=='http://localhost':
		new_url = webnotes.conn.get_value('Website Settings', 'Website Settings',
			'subdomain')
		if new_url:
			url = "http://" + new_url
			
	return url