import logging

from oatsutils import extract_csv_header

total_apc_field = 'Total APC amount'

class CoafFieldsMapping():
    '''
    Mapping of column names in CUFS reports of COAF spending.
    '''
    def __init__(self):
        self.field_names = extract_csv_header(coaf_paymentsfile, "utf-8")
        self.amount_field = 'Burdened Cost'
        self.invoice_field = 'Invoice'
        self.oa_number =  'Comment'
        self.paydate_field = 'GL Posting Date'
        self.total_apc = 'COAF APC Amount' #Name of field we want the calculated total COAF APC to be stored in
        self.total_other = 'COAF Page, colour or membership amount'  # Name of field we want the total for other costs to be stored in
        self.transaction_code = 'Tran'

class RcukFieldsMapping():
    '''
    Mapping of column names in CUFS reports of RCUK spending.
    '''
    def __init__(self):
        self.field_names = extract_csv_header(rcuk_paymentsfile, "utf-8")
        self.amount_field = 'Amount'
        self.invoice_field = 'Ref 5'
        self.oa_number =  'Description'
        self.paydate_field = 'Posted'
        self.total_apc = 'RCUK APC Amount'  # Name of field we want the calculated total RCUK APC to be stored in
        self.total_other = 'RCUK Page, colour or membership amount'  # Name of field we want the total for other costs to be stored in
        self.transaction_code = 'Tran'

class Parser():
    '''
    Parser for CUFS exports.
    Use this class to read in data exported from CUFS and parse it into a number of
    dictionaries.
    '''

    def __init__(self, oa2zd_dict):
        '''

        :param oa2zd_dict: A dictionary mapping OA numbers to ZD numbers
        '''
        ### USE THIS DICTIONARY TO FORCE THE MAPPING OF PARTICULARLY PROBLEMATIC OA NUMBERS TO ZD NUMBERS
        ### FOR EXAMPLE A OA NUMBER MARKED AS DUPLICATE IN ZENDESK, BUT WITH A PAYMENT ASSOCIATED WITH IT
        ### (SO NOT EASY TO FIX IN ZENDESK)
        self.manual_oa2zd_dict = {
                                'OA-1128':'3743',
                                'OA-1515':'4323',
                                'OA-13907':'83033',
                                'OA-10518':'36495',
                                'OA-13111':'76842',
                                'OA-14062':'86232',
                                'OA-13919':'83197',
                                'OA-14269':'89212'
                                }
        self.oa2zd_dict = oa2zd_dict



    def plug_in_payment_data(self, paymentsfile, fileheader, oa_number_field, output_apc_field, output_pagecolour_field,
                             invoice_field='Ref 5', amount_field='Amount', file_encoding='charmap',
                             transaction_code_field='Tran',
                             source_funds_code_field='SOF', funder='RCUK'):
        '''
        This function parses financial reports produced by CUFS. It tries to mach each payment in the CUFS report
        to a zd ticket and, if successful, it produces summations of payments per zd ticket and appends these
        values to zd_dict as output_apc_field and/or output_pagecolour_field

        :param paymentsfile: path of input CSV file containing payment data
        :param fileheader: header of input CSV file
        :param oa_number_field: name of field in input file containing "OA-" numbers
        :param output_apc_field: name of field to output summed APC payments to
        :param output_pagecolour_field: name of field to output summed page/colour payments to
        :param invoice_field: name of field in input file containing invoice numbers
        :param amount_field: name of field in input file containing the amount of each payment
        :param file_encoding: enconding of input file
        :param transaction_code_field: name of field in input file containing the transaction code
                                        for APC payments (EBDU) or page/colour (EBDV)
        :param source_funds_code_field: name of field in input file containing the source of funds code (JUDB)
        :param funder: funder who requested this report (e.g. RCUK / COAF)
        '''
        t_oa = re.compile("OA[ \-]?[0-9]{4,8}")
        t_zd = re.compile("ZD[ \-]?[0-9]{4,8}")
        payments_dict_apc = {}
        payments_dict_other = {}
        with open(paymentsfile, encoding=file_encoding) as csvfile:
            reader = csv.DictReader(csvfile)
            row_counter = 0
            for row in reader:
                if row[oa_number_field] in oa_number_typos.keys():
                    row[oa_number_field] = oa_number_typos[row[oa_number_field]]
                m_oa = t_oa.search(row[oa_number_field].upper())
                m_zd = t_zd.search(row[oa_number_field].upper())
                if m_oa:
                    oa_number = m_oa.group().upper().replace("OA", "OA-").replace(" ", "")
                    try:
                        zd_number = self.manual_oa2zd_dict[oa_number]
                    except KeyError:
                        try:
                            zd_number = self.oa2zd_dict[oa_number]
                        except KeyError:
                            logging.warning(('A ZD number could not be found for {} in {}. Data for this OA number'
                                            ' will NOT be exported'.format(oa_number, paymentsfile)))
                            zd_number = ''
                elif m_zd:
                    zd_number = m_zd.group().replace(" ", "-").strip('ZDzd -')
                else:
                    zd_number = ''

                if row[invoice_field].strip() in invoice2zd_number.keys():
                    zd_number = invoice2zd_number[row[invoice_field]]

                if row[oa_number_field].strip() in description2zd_number.keys():
                    zd_number = description2zd_number[row[oa_number_field]]

                if zd_number:
                    if zd_number in zd_number_typos.keys():
                        zd_number = zd_number_typos[zd_number]
                    # print('zd_number:', zd_number)
                    if transaction_code_field in row.keys():
                        ##PAYMENTS SPREADSHEET CONTAINS TRANSACTION FIELD
                        if row[source_funds_code_field] == 'JUDB':
                            if row[transaction_code_field] == 'EBDU':
                                if funder == 'RCUK':
                                    key = 'EBDU_' + str(row_counter)
                                    included_rcuk_payment_dict[key] = row.copy()
                                if zd_number in payments_dict_apc.keys():
                                    ### ANOTHER APC PAYMENT WAS ALREADY RECORDED FOR THIS ZD
                                    ### NUMBER, SO WE CONCATENATE VALUES
                                    existing_payment = payments_dict_apc[zd_number]
                                    p_amount = float(existing_payment[output_apc_field].replace(',', ''))
                                    n_amount = float(row[amount_field].replace(',', ''))
                                    balance = str(p_amount + n_amount)
                                    for k in row.keys():
                                        if (existing_payment[k] != row[k]) and (k not in [rcuk_paydate_field,
                                                                                          coaf_paydate_field]):  # DO NOT CONCATENATE PAYMENT DATES
                                            n_value = existing_payment[k] + ' %&% ' + row[k]
                                        else:
                                            n_value = row[k]
                                        payments_dict_apc[zd_number][k] = n_value
                                    payments_dict_apc[zd_number][output_apc_field] = balance
                                else:
                                    ###STORE APC PAYMENT INFO INDEXED ON ZD NUMBER
                                    payments_dict_apc[zd_number] = row
                                    payments_dict_apc[zd_number][output_apc_field] = payments_dict_apc[zd_number][
                                        amount_field]
                                ### NOW THAT WE DEALT WITH THE PROBLEM OF SEVERAL APC PAYMENTS
                                ### FOR EACH ZD NUMBER, ADD PAYMENT INFO TO MASTER DICT
                                ### OF ZD NUMBERS
                                for field in payments_dict_apc[zd_number].keys():
                                    if (field in zd_dict[zd_number].keys()) and (row_counter == 0):
                                        print('WARNING: Dictionary for ZD ticket', zd_number,
                                              'already contains a field named',
                                              field + '. It will be overwritten by the value in file', paymentsfile)
                                zd_dict[zd_number].update(payments_dict_apc[
                                                              zd_number])  # http://stackoverflow.com/questions/8930915/append-dictionary-to-a-dictionary
                            elif row[transaction_code_field] in ['EBDV', 'EBDW']:
                                if funder == 'RCUK':
                                    key = 'EBDV-W_' + str(row_counter)
                                    included_rcuk_payment_dict[key] = row.copy()
                                if zd_number in payments_dict_other.keys():
                                    ### ANOTHER PAGE/MEMBERSHIP PAYMENT WAS ALREADY RECORDED FOR THIS ZD
                                    ### NUMBER, SO WE CONCATENATE VALUES
                                    existing_payment = payments_dict_other[zd_number]
                                    p_amount = float(existing_payment[output_pagecolour_field].replace(',', ''))
                                    n_amount = float(row[amount_field].replace(',', ''))
                                    balance = str(p_amount + n_amount)
                                    for k in row.keys():
                                        if (existing_payment[k] != row[k]) and (
                                            k not in [rcuk_paydate_field, coaf_paydate_field, transaction_code_field]):
                                            n_value = existing_payment[k] + ' %&% ' + row[k]
                                        elif k == transaction_code_field:  # special treatment for this case necessary to avoid overwriting preexisting APC transaction code (EBDU); concatenate with value in apc dict
                                            try:
                                                if payments_dict_apc[zd_number][k]:
                                                    n_value = payments_dict_apc[zd_number][k] + ' %&% ' + row[k]
                                                else:
                                                    n_value = row[k]
                                            except KeyError:
                                                n_value = row[k]
                                        else:
                                            n_value = row[k]
                                        payments_dict_other[zd_number][k] = n_value
                                    payments_dict_other[zd_number][output_pagecolour_field] = balance
                                else:
                                    ###STORE PAGE/MEMBERSHIP PAYMENT INFO INDEXED ON ZD NUMBER
                                    payments_dict_other[zd_number] = row
                                    payments_dict_other[zd_number][output_pagecolour_field] = \
                                    payments_dict_other[zd_number][amount_field]
                                ### NOW THAT WE DEALT WITH THE PROBLEM OF SEVERAL PAGE/MEMBERSHIP PAYMENTS
                                ### FOR EACH ZD NUMBER, ADD PAYMENT INFO TO MASTER DICT
                                ### OF ZD NUMBERS
                                for field in payments_dict_other[zd_number].keys():
                                    if (field in zd_dict[zd_number].keys()) and (row_counter == 0):
                                        print('WARNING: Dictionary for ZD ticket', zd_number,
                                              'already contains a field named',
                                              field + '. It will be overwritten by the value in file', paymentsfile)
                                zd_dict[zd_number].update(payments_dict_other[
                                                              zd_number])  # http://stackoverflow.com/questions/8930915/append-dictionary-to-a-dictionary
                            else:
                                ## NOT A EBDU, EBDV OR EBDW PAYMENT
                                key = 'not_EBD*_payment_' + str(row_counter)
                                if funder == 'RCUK':
                                    rejected_rcuk_payment_dict[key] = row
                                debug_filename = os.path.join(working_folder,
                                                              nonEBDU_payment_file_prefix + paymentsfile.split('/')[-1])
                                output_debug_info(debug_filename, row, fileheader)
                        else:
                            ## NOT A JUDB PAYMENT
                            key = 'not_JUDB_payment_' + str(row_counter)
                            if funder == 'RCUK':
                                rejected_rcuk_payment_dict[key] = row
                            debug_filename = nonJUDB_payment_file_prefix + paymentsfile
                            output_debug_info(debug_filename, row, fileheader)
                    else:
                        ##PAYMENTS SPREADSHEET DOES NOT CONTAIN TRANSACTION FIELD
                        ##WE MUST ASSUME ALL PAYMENTS ARE APCs
                        key = 'no_transaction_field_' + str(row_counter)
                        if funder == 'RCUK':
                            included_rcuk_payment_dict[key] = row.copy()
                            plog(
                                'WARNING: RCUK payments without a transaction field detected. Something is probably wrong!')
                        elif funder == 'COAF':
                            included_coaf_payment_dict[key] = row.copy()
                        if zd_number in payments_dict_apc.keys():
                            ### ANOTHER APC PAYMENT WAS ALREADY RECORDED FOR THIS ZD
                            ### NUMBER, SO WE CONCATENATE VALUES
                            existing_payment = payments_dict_apc[zd_number]
                            p_amount = float(existing_payment[output_apc_field].replace(',', ''))
                            n_amount = float(row[amount_field].replace(',', ''))
                            balance = str(p_amount + n_amount)
                            for k in row.keys():
                                if (existing_payment[k] != row[k]) and (k not in [rcuk_paydate_field, coaf_paydate_field]):
                                    n_value = existing_payment[k] + ' %&% ' + row[k]
                                else:
                                    n_value = row[k]
                                payments_dict_apc[zd_number][k] = n_value
                            payments_dict_apc[zd_number][output_apc_field] = balance
                        else:
                            ###STORE APC PAYMENT INFO INDEXED ON ZD NUMBER
                            payments_dict_apc[zd_number] = row
                            try:
                                payments_dict_apc[zd_number][output_apc_field] = payments_dict_apc[zd_number][amount_field]
                            except KeyError:
                                print('WARNING: Could not determine amount of payment for ticket below. Using ZERO:')
                                pprint(payments_dict_apc[zd_number])
                                payments_dict_apc[zd_number][output_apc_field] = '0'
                        ### NOW THAT WE DEALT WITH THE PROBLEM OF SEVERAL APC PAYMENTS
                        ### FOR EACH ZD NUMBER, ADD PAYMENT INFO TO MASTER DICT
                        ### OF ZD NUMBERS
                        for field in payments_dict_apc[zd_number].keys():
                            if (field in zd_dict[zd_number].keys()) and (row_counter == 0):
                                print('WARNING: Dictionary for ZD ticket', zd_number, 'already contains a field named',
                                      field + '. It will be overwritten by the value in file', paymentsfile)
                        zd_dict[zd_number].update(payments_dict_apc[
                                                      zd_number])  # http://stackoverflow.com/questions/8930915/append-dictionary-to-a-dictionary
                else:
                    ## PAYMENT COULD NOT BE LINKED TO A ZENDESK NUMBER
                    key = 'no_zd_match_' + str(row_counter)
                    if funder == 'RCUK':
                        rejected_rcuk_payment_dict[key] = row
                    elif funder == 'COAF':
                        rejected_coaf_payment_dict[key] = row
                    debug_filename = os.path.join(working_folder,
                                                  unmatched_payment_file_prefix + paymentsfile.split('/')[-1])
                    output_debug_info(debug_filename, row, fileheader)
                row_counter += 1