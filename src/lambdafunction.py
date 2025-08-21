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
import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from botocore.config import Config
from botocore.session import Session
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pypdf import PdfWriter, PdfReader
import json

def lambda_handler(event,context):
    
    try:
        if 'body' in event and isinstance(event['body'], str):
            # Parse the JSON string from the 'body' key
            print(event)
            payload = json.loads(event['body'])

            events = {
                "date": payload.get("date"),
                "tfNo": payload.get("tfNo"),
                "cpr": payload.get("cpr"),
                "customerID":payload.get("customerID"),
                "email":payload.get("email"),
                "header": payload.get("header"),
                "msgColumn1": payload.get("msgColumn1",None),
                "msgColumn2": payload.get("msgColumn2",None),
                "customerName": payload.get("customerName"),
                "sender": payload.get("sender"),
                "receiver": payload.get("receiver")
               
            }
        else:
            # Handle cases where the body is missing or in an unexpected format
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Request body missing or invalid."})
            }

        if not all([events["cpr"], events["email"],events["customerID"]]):
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Inadequate details."})
            }
        
        return generate_pdf(events,context)    
    except json.JSONDecodeError:
        # Handle malformed JSON in the request body
        return {
            "statusCode": 400,
            "body": json.dumps({"message": "Invalid JSON in request body."})
        }

    except Exception as e:
        # Log the full exception for debugging
        print(f"An unexpected error occurred: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error."})
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
    logo_path = 'images/ASB_Logo.png'
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
    stamp_path = 'images/ASB_Stamp.png' # Make sure this image exists
    try:
        page_width = letter[0]
        
        width, height = letter

        x = (width - 100) / 2
        y = height - 50 - 50  # Position near top (header area)

        canvas.drawImage(stamp_path, x, 80, width=80, height=50)

        # canvas.drawImage(stamp_path, page_width - 1.5 * inch, 0.6 * inch, width=0.75 * inch, height=0.75 * inch)
    except Exception:
        canvas.drawString(page_width - 2 * inch, 0.7 * inch, "[Stamp Placeholder]")

    footer_path = 'images/footer.png' # Make sure this image exists
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

            response = send_email_with_attachment_base64("no-reply-dev@alsalambank.com", events["email"], "MT700 SWIFT DETAILS", protected_pdf_buffer.getvalue(),pdf_filename)
            
            if response["statusCode"] == 200:
                return  {
                    'statusCode': 200,
                    'body':  json.dumps({"message": response["body"]})
                    }
            else:
                return  {
                    "statusCode": 500,
                    "body": json.dumps({"message":response["body"]})
                    }
        except Exception as e:
            return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error."})
            }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"message": "Internal Server Error."})
        }

def send_email_with_attachment_base64(sender, recipient, subject, base64_string,fileName):
    
    try:
        msg = MIMEMultipart()
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = recipient

        with open("emailBody.html", "r", encoding="utf-8") as file:
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
        print(response['MessageId'])
        return {
            'statusCode': 200,
            'body': f"Email sent! Message ID: {response['MessageId']}"
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': f"Email send failed: {str(e)}"
        }
 