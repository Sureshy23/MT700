from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, LongTable,TableStyle, Paragraph
from reportlab.lib.units import inch
from reportlab.lib import colors
import base64
import io
from reportlab.lib.colors import lightgrey,darkgray
import html
import datetime
import pyperclip
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from botocore.config import Config
from botocore.session import Session
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pypdf import PdfWriter, PdfReader


def lambda_handler(event,context):
    
    try:
        events = {

                "date": event["date"],
                "tfNo": event["tfNo"],
                "cpr": event["cpr"],
                "customerID":event["customerID"],
                "email":event["email"],
                "header": event["header"],
                "msgColumn1": event.get("msgColumn1",None),
                "msgColumn2": event.get("msgColumn2",None),
                "customerName": event["customerName"],
                "sender": event["sender"],
                "receiver": event["receiver"]
               
            }
        
        return generate_pdf(events,context)    

    except Exception as e:
        print(e)
        return {
            'statusCode': 500,
            'body':  str(e)
        }

def my_custom_layout(canvas, doc,refNo, name):
    canvas.saveState()
    styles = getSampleStyleSheet()

    # --- HEADER ---
    # Left-aligned text
    canvas.setFont('Helvetica-Bold', 12)
    canvas.setFillColor(colors.black)
    canvas.drawString(inch*0.7, letter[1] - 0.5 * inch, "Swift Advice")

    # Right-aligned logo
    logo_path = 'ASB_Logo.png'
    try:
        # Get the width and height of the page for positioning
        page_width = letter[0]
        # Position the image: (x, y, width, height)
        # We subtract from the page width to align it to the right
        canvas.drawImage(logo_path, page_width - 2 * inch, letter[1] - 0.6 * inch, width=1.5 * inch, height=0.45 * inch)
    except Exception:
        canvas.drawString(page_width - 2 * inch, letter[1] - 0.75 * inch, "Alsalam Bank")
   
    page_width, page_height = letter
    y_line_position = page_height - 50
    # letter[1] - 10 * inch  # Position the line below the primary header
    x_start = 0.7 * inch
    x_end = letter[0] - inch *0.50
    text_to_print = "Reference No: "+ refNo
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(colors.darkgrey)
    text_width = canvas.stringWidth(text_to_print, 'Helvetica', 9)

    # Calculate line endpoints with padding
    line1_end_x = (x_start + x_end) / 2 - (text_width / 2) - 5
    line2_start_x = (x_start + x_end) / 2 + (text_width / 2) + 5
    text_x_pos = (x_start + x_end) / 2 - (text_width / 2)

    # Draw the first half of the line
    canvas.setStrokeColor(colors.darkgrey)
    canvas.line(x_start, y_line_position, line1_end_x, y_line_position)

    # Print the text
    canvas.drawString(text_x_pos, y_line_position - 4, text_to_print) # Adjust y for vertical alignment

    # Draw the second half of the line
    canvas.line(line2_start_x, y_line_position, x_end, y_line_position)

    canvas.setFont('Helvetica-Bold', 8)
    canvas.setFillColor(colors.darkgrey)
    canvas.drawString(inch*0.7, letter[1] - 0.9 * inch, name)

   
    line_y = page_height - 90  # Position near the top
    canvas.setLineWidth(20)
    canvas.setStrokeColor(colors.black)
    canvas.line(50, line_y, page_width - 35, line_y)
    
    text = "SWIFT Details"
    canvas.setFont("Helvetica-Bold", 10)
    text_width = canvas.stringWidth(text, "Helvetica-Bold", 10)
    canvas.setFillColor(colors.white)
    canvas.drawString(inch*0.7, line_y - 4, text)

    # --- FOOTER ---
    # Centered page number
    canvas.setFont('Helvetica', 6)
    canvas.setFillColor(colors.darkgray)
    # canvas.drawCentredString(letter[0] / 2.0, 0.5 * inch, f"Page {canvas.getPageNumber()}")

    footer_text = ["This is a Computer Generated Document. Any issues relating to the displayed information must be communicated within 30 days.",
                    "Al Salam Bank Bahrain, Licensed and Regulated by the Central Bank of Bahrain as an Islamic Retail Bank",
                      "Call Center: +973 1700 5500 | Email: call-centerteam@alsalambahrain.com"]
    y_position = 0.9 * inch
    x_pos = 100    
    for line in footer_text:
        canvas.drawString(x_pos, y_position, line)
        y_position -= 0.10 * inch # Adjust spacing between lines
        x_pos = x_pos+30

    # Right-aligned stamp image
    stamp_path = 'ASB_Stamp.png' # Make sure this image exists
    try:
        page_width = letter[0]
        
        width, height = letter

        x = (width - 100) / 2
        y = height - 50 - 50  # Position near top (header area)

        canvas.drawImage(stamp_path, x, 80, width=80, height=50)

        # canvas.drawImage(stamp_path, page_width - 1.5 * inch, 0.6 * inch, width=0.75 * inch, height=0.75 * inch)
    except Exception:
        canvas.drawString(page_width - 2 * inch, 0.7 * inch, "[Stamp Placeholder]")

    footer_path = 'footer.png' # Make sure this image exists
    try:
        page_width = letter[0]
        canvas.drawImage(footer_path, 0, 0, width=page_width, height=0.6*inch)
    except Exception:
        canvas.drawString(page_width - 2 * inch, 0.7 * inch, "[Stamp Placeholder]")

    canvas.restoreState()

def generate_pdf(events, context):
    try:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,bottomMargin=120,topMargin=100)
        
        styles = getSampleStyleSheet()

        data = []  # header

        cl1 = events["msgColumn1"]
        cl2 = events["msgColumn2"]

        grouped_dict = {}
        current_cl1 = None

        for i in range(len(cl1)):
            if cl1[i].strip():
                current_cl1 = cl1[i].strip()
                grouped_dict[current_cl1] = []

            if current_cl1 is not None:
                if cl2[i] != ' ' and cl2[i] != '':
                    grouped_dict[current_cl1].append(cl2[i].strip())

        MAX_LINES_PER_CELL = 8  # arbitrary threshold before splitting

        data = []
        normal_style = styles['Normal']
        normal_style = ParagraphStyle(name='CenterBold', fontName='Helvetica', fontSize=8)

        for cl1_val, cl2_list in grouped_dict.items():
            cl2_paragraph = Paragraph("<br/>".join(cl2_list), normal_style)
            data.append([cl1_val, cl2_paragraph])
            # if len(cl2_list) <= MAX_LINES_PER_CELL:
            #     # Short enough to keep in one cell
            #     cl2_para = Paragraph("<br/>".join(cl2_list), styles['Normal'])
            #     data.append([cl1_val, cl2_para])
            # else:
            #     # Split into multiple rows to avoid crashing
            #     first = True
            #     for item in cl2_list:
            #         data.append([cl1_val if first else "", Paragraph(item, styles['Normal'])])
            #         first = False
     
        table = LongTable(data, colWidths=[3.1 * inch, 4.0 * inch])  # two columns

        table.setStyle(TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),

            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),

            # Make inner grid and box invisible too
            ('INNERGRID', (0, 0), (-1, -1), 1, colors.white),
            ('BOX', (0, 0), (-1, -1), 0.25, colors.white),
            ('LINEBEFORE', (1, 0), (1, -1), 1, colors.white), 
        ]))     

        for row_num in range(0, len(data)):
            if row_num % 2 == 0:  # even rows (2,4,6...)
                bg_color = colors.HexColor('#f4f5f9') 
            else:  # odd rows (1,3,5...)
                bg_color = colors.white

            table.setStyle(TableStyle([
                ('BACKGROUND', (0, row_num), (-1, row_num), bg_color),
            ]))

        paragraphs = [table]

        # Build the PDF
        doc.onFirstPage = lambda canvas, doc: my_custom_layout(canvas, doc, events["tfNo"], events["customerName"])
        doc.onLaterPages = lambda canvas, doc: my_custom_layout(canvas, doc, events["tfNo"], events["customerName"])

        doc.build(paragraphs)

        # Get the PDF data from the buffer
        pdf_data = buffer.getvalue()
        # buffer.close()

        # Move the buffer's position to the beginning so pypdf can read it
        buffer.seek(0)
        
        # Read the ReportLab-generated PDF with pypdf
        reader = PdfReader(buffer)
        writer = PdfWriter()

        # Add all pages from the original PDF to the writer
        for page in reader.pages:
            writer.add_page(page)

        # Encrypt the PDF with the provided password
        writer.encrypt(user_password=events["cpr"]+events["customerID"], owner_password=None, permissions_flag=0)

        # Create a new buffer for the protected PDF and save the encrypted content
        protected_pdf_buffer = io.BytesIO()
        writer.write(protected_pdf_buffer)
        protected_pdf_buffer.seek(0)                                        
        # buffer.close()
        # protected_pdf_buffer.close()

        # Encode the PDF data to Base64
        base64_pdf = base64.b64encode(protected_pdf_buffer.getvalue()).decode('utf-8')
        pdf_filename = "SwiftAdvice_"+events["tfNo"]+".pdf"
        try:
            response = send_email_with_attachment_base64("no-reply-dev@alsalambank.com", events["email"][0], "MT700 SWIFT DETAILS", base64_pdf,pdf_filename)
            if response["statusCode"] == 200:
                return  {
                    'statusCode': 200,
                    'body':  response["body"]
                    }
        except Exception as e:
            return  {
                    'statusCode': 500,
                    'body': str(e)
                    }

        file_name = events["tfNo"]+".pdf"
        pyperclip.copy(base64_pdf)
        data ={ "messageId": ""}
        return {
            'statusCode': 200,
            'body':data     
        }

    except Exception as e:
        print(str(e))
        return {
            'statusCode': 500,
            'body':str(e)
        }

def send_email_with_attachment_base64(sender, recipient, subject, base64_string,fileName):
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        with open("emailbody.html", "r", encoding="utf-8") as file:
            html_content = file.read()

        html_content = html_content.replace("{{subject}}", subject)

        msg.attach(MIMEText(html_content, 'html'))    

        pdf_attachment = MIMEApplication(base64_string)
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename=fileName)
        msg.attach(pdf_attachment)

        ses_client = boto3.client('ses')
        
        response = ses_client.send_raw_email(
                Source=msg['From'],
                Destinations=[msg['To']],
                RawMessage={'Data': msg.as_string()}
                
        )
        return {
            'statusCode': 200,
            'body': f"Email sent! Message ID: {response['MessageId']}"
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Email send failed: {str(e)}"
        }
   


if __name__ == "__main__":
    test_event = {
  "fromEmail":"no-reply-dev@alsalambank.com",
  "date": "18 JUN 2025",
  "tfNo": "TF2516923757",
  "cpr": "76358-1",
  "customerID": "819914",
  "email": "os.yedlapalle@alsalambank.com",
  "header": "MT700",
  "customerName": "Short Name 819914",
  "sender": "ALSXXXXX",
  "receiver": "NBFXXXXX Name 1 - 500061 KHAXXXXX P.OXXXXX DUBXXXXX UNIXXXXX",
  "msgColumn1": [
    "27:Sequence of Total",
    "40A:FORM OF DOCUMENTARY CREDIT",
    "20:Sender's Reference",
    "31C:Date of Issue",
    "40E:Applicable Rules",
    "31D:Date and place of Expiry",
    "50:Applicant",
    "",
    "",
    "",
    "59:Beneficiary Customer-Name & Addr",
    "",
    "",
    "32B:Currency Code, Amount",
    "41A:Available With ...BY...",
    "",
    "42C:Drafts at",
    "42A:Drawee",
    "43P:Partial Shipment",
    "43T:Transhipment",
    "44E:Port of Loading / Airport",
    "44F:Port of Discharge / Airport",
    "44C:Latest Date of Shipment",
    "45A:Description of Goods and/or Service",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "46A:Documents Required",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "47A:Additional Conditions",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "71D:Charges",
    "",
    "",
    "48:Period for Presentation in Days",
    "49:Confirmation Instruction",
    "58A:Requested Confirmation Party",
    "78:Instructions to the PAY/APT/NEG BNK",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    "",
    ""
  ],
  "msgColumn2": [
    "1/1 ",
    "IRREVOCABLE ",
    "TF2516923757 ",
    "250129 ",
    "UCP LATEST VERSION ",
    "280315UAE ",
    "NOFA MARINE SERVICES CO WLL ",
    "OFFICE 670, DRY DOCK HIGHWAY, ",
    "0116 HIDD, P.O. BOX 5021, ",
    "MUHARRAQ, KINGDOM OF BAHRAIN ",
    "/AE880380000012001393877 ",
    "CHARTERBULK SHIPPING D.M.C.C. ",
    "P.O. BOX 232039, DUBAI, U.A.E. ",
    "USD365917,50 ",
    "NBFXXXXX ",
    "BY PAYMENT ",
    "SIGHT ",
    "ALSXXXXX ",
    "NOT ALLOWED ",
    "NOT ALLOWED ",
    "ANY PORT IN UNITED ARAB EMIRATES ",
    "ASRY HIDD PORT, KINGDOM OF BAHRAIN ",
    "250215 ",
    "LIMESTONE AGGREGATES IN BULK 5-10MM AND 10-20MM ",
    "QUANTITY MINIMUM 27,000 MT TO MAXIMUM 30,000 MT IN SELLERS",
    "OPTION. ALL OTHER DETAILS AS PER BENEFICIARY'S ",
    "PROFORMA INVOICE NO. CB/NOFA/01/2025/001, DATED 12.01.2025. ",
    "",
    "INCOTERMS CFR, KINGDOM OF BAHRAIN.",
    " ",
    "SHIPPING MARKS NOFA MARINE SERVICES CO WLL",
    " ",
    "INVOICE TO CERTIFY SO. ",
    "/REPALL/1. SIGNED COMMERCIAL INVOICE IN ONE ORIGINAL AND TWO ",
    "COPIES ",
    "EVIDENCING SHIPMENT OF GOODS DESCRIBED HEREIN ON CFR BASIS ",
    "SHOWING ORIGIN OF THE GOODS AND THE NAME AND THE ADDRESS OF THE ",
    "PRODUCER / MANUFACTURER OF THE MERCHANDISE. ",
    " ",
    "2. FULL SET SIGNED CLEAN ON BOARD OCEAN BILLS OF LADING ",
    "MADE OUT TO THE ORDER OF AL SALAM BANK BSC, P.O.BOX ",
    "18282, MANAMA, KINGDOM OF BAHRAIN, MARKED FREIGHT PREPAID AND ",
    "NOTIFY THE APPLICANT. BILLS OF LADING SHOULD STATE NAME AND ",
    "ADDRESS OF THE CARRIERS AGENT AT PLACE OF DELIVERY THIS CREDIT ",
    "NUMBER AND QUANTITY OF GOODS. ",
    " ",
    "3.CERTIFICATE OF UAE ORIGIN IN ONE ORIGINAL AND ONE ",
    "COPY ISSUED BY UNITED ARAB EMIRATES MINISTRY OF ECONOMY ",
    "ORIGIN DEPARTMENT AND TO BE DULY LEGALIZED / ATTESTED BY ",
    "CHAMBER OF COMMERCE ONLY. ",
    " ",
    "4. PACKING LIST IN ONE ORIGINAL AND TWO COPIES. ",
    " ",
    "5. QUALITY CERTIFICATE OF AGGREGATE ISSUED BY ",
    "AL HOTY STRANGER LABORATIES U.A.E. ",
    " ",
    "6. DRAFT AND DISPLACEMENT SURVEY OF THE VESSEL AT LOADING PORT, ",
    "WHERE THE SURVEYOR WILL BE DULY APPOINTED BY ANY U.A.E. PORT. ",
    " ",
    "7. CERTIFICATE ISSUED BY SHIPPING COMPANY OR THEIR AGENT ",
    "CERTIFYING THAT ",
    "(A) THE CARRYING VESSEL IS REGULAR LINE VESSEL. ",
    "(B) AGE OF CARRYING VESSEL DOES NOT EXCEED 18 YEARS. ",
    "(C) THE VESSEL IS NOT PROHIBITED FROM ENTERING INTO ARAB PORTS ",
    "FOR ANY REASONS PURSUANT TO ITS LAWS AND REGULATIONS. ",
    "(D) THE CARRYING VESSELS IS SUBJECT TO THE INTERNATIONAL SAFETY ",
    "MANAGEMENT CODE (ISM). ",
    " ",
    "1. ALL DOCUMENTS DRAWN UNDER THIS LC TO INDICATE THE LC NUMBER ",
    "AND THE NAME OF THE ISSUING BANK UNLESS OTHERWISE EXPRESSLY ",
    "STATED EXCEPT FOR ANY 3RD PARTY DOCUMENTS / ISSUED BY UAE ",
    "MINISTRY OF ECONOMY. ",
    " ",
    "2. IN THE EVENT THAT THE DOCUMENTS DRAWN UNDER THIS LC, WHETHER ",
    "PRESENTED UNDER LC OR ON COLLECTION OR ON APPROVAL BASIS, ARE ",
    "FOUND TO BE NOT IN COMPLIANCE OF LC TERMS AND CONDITIONS, WE ",
    "SHALL, AT OUR SOLE DISCRETION, APPROACH THE APPLICANT FOR A ",
    "WAIVER OF THE DISCREPANCIES. SHOULD THE APPLICANT WAIVE THESE ",
    "DISCREPANCIES AND IN THE EVENT THAT SUCH WAIVER IS ACCEPTABLE TO ",
    "US, WE SHALL DELIVER THE DOCUMENTS TO THE APPLICANT AND DEDUCT ",
    "OUR DISCREPANCY FEE PLUS OUR HANDLING FEE AND ANY OTHER OUT OF ",
    "POCKET EXPENSES FROM THE BILL AMOUNT. ",
    " ",
    "3. ALL DOCUMENTS MUST BE DATED AND ISSUED IN ENGLISH AND OR ",
    "ARABIC LANGUAGE. ANY DOCUMENT DATED PRIOR TO THE ",
    "ISSUANCE DATE OF THIS CREDIT IS NOT ACCEPTABLE. ",
    " ",
    "4. BENEFICIARY IS NOT ALLOWED TO PRESENT THE DOCUMENTS DIRECTLY ",
    "TO THE ISSUING BANK. PRESENTATION OF DOCUMENTS TO THE ISSUING ",
    "BANK IS RESTRICTED TO BANKS ONLY. ",
    " ",
    "5. DOCUMENTS TO BE PRESENTED WITHIN 30 DAYS FROM DATE OF ",
    "SHIPMENT BUT WITHIN THE VALIDITY OF CREDIT. ",
    " ",
    "ALL CHARGES OUTSIDE BAHRAIN ARE ",
    "FOR THE ACCOUNT OF BENEFICIARY ",
    "INCLUDING THE CONFIRMATION CHARGES ",
    "30/DAYS FROM THE DATE OF SHIPMENT ",
    "CONFIRM ",
    "NBFXXXXX ",
    "1. ALL DOCUMENTS UNDER THIS LC SHOULD BE COURIERED TO US IN ",
    "ONE LOT AT THE FOLLOWING ADDRESS AL SALAM BANK B.S.C.,",
    "HEAD OFFICE, TRADE FINANCE OPS, FLAT 101, BUILDING 935, ROAD ",
    "1015, BLOCK SANABIS 410, KINGDOM OF BAHRAIN. ",
    " ",
    "2.UPON RECEIPT OF DOCUMENTS COMPLYING WITH LC TERMS AND ",
    "CONDITIONS WE SHALL REMIT THE BILL AMOUNT AS PER THE ",
    "INSTRUCTIONS OF THE PRESENTING BANK, LESS BY OUR CHARGES (IF ",
    "ANY). ",
    " ",
    "-} ",
    ""
  ]
}


lambda_handler(test_event, {})