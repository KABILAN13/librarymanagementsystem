from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import HttpResponse
from .models import Checkout

def generate_issued_pdf(request):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="issued_books.pdf"'
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    
    # Draw things on the PDF
    p.drawString(100, 750, "Currently Issued Books Report")
    p.drawString(100, 730, "Generated on: " + timezone.now().strftime("%Y-%m-%d"))
    
    # Add table data
    y = 700
    checkouts = Checkout.get_issued_books_report()
    for checkout in checkouts:
        p.drawString(100, y, f"{checkout.book.title} - {checkout.member.get_full_name()}")
        y -= 20
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response