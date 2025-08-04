from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from weasyprint import HTML, CSS
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
from datetime import datetime
import uvicorn
from num2words import num2words

app = FastAPI(title="PDF Generation Service", version="1.0.0")

# Pydantic models matching your NestJS DTOs
class CompanyInfo(BaseModel):
    raisonSociale: str = Field(default=..., json_schema_extra={"examples": ["ABC Company SARL"]})
    adresse: str = Field(default=..., json_schema_extra={"examples": ["123 Rue Example, Alger"]})
    telephone: str = Field(default=..., json_schema_extra={"examples": ["+213 555 123 456"]})
    email: Optional[str] = Field(default=None, json_schema_extra={"examples": ["contact@abc.com"]})
    nif: str = Field(default=..., json_schema_extra={"examples": ["123456789012345"]})
    nis: str = Field(default=..., json_schema_extra={"examples": ["123456789012345"]})
    rc: str = Field(default=..., json_schema_extra={"examples": ["12345678"]})
    art: Optional[str] = Field(default=None, json_schema_extra={"examples": ["123456789"]})

class ClientInfo(BaseModel):
    nom: str = Field(default=..., json_schema_extra={"examples": ["Client XYZ"]})
    adresse: str = Field(default=..., json_schema_extra={"examples": ["456 Rue Client, Oran"]})
    telephone: Optional[str] = Field(default=None, json_schema_extra={"examples": ["+213 555 987 654"]})
    nif: Optional[str] = Field(default=None, json_schema_extra={"examples": ["987654321098765"]})
    nis: Optional[str] = Field(default=None, json_schema_extra={"examples": ["987654321098765"]})
    art: Optional[str] = Field(default=None, json_schema_extra={"examples": ["987654321"]})

class DocumentInfo(BaseModel):
    numero: str = Field(default=..., json_schema_extra={"examples": ["BL-2024-001"]})
    date: str = Field(default=..., json_schema_extra={"examples": ["2024-01-15"]})
    bonCommande: Optional[str] = Field(default=None, json_schema_extra={"examples": ["BC-2024-001"]})
    dateLivraison: Optional[str] = Field(default=None, json_schema_extra={"examples": ["2024-01-20"]})
    dateEcheance: Optional[str] = Field(default=None, json_schema_extra={"examples": ["2024-02-15"]})
    conditions: Optional[str] = Field(default=None, json_schema_extra={"examples": ["Paiement à 30 jours"]})
    modePaiement: Optional[str] = Field(default=None, json_schema_extra={"examples": ["Virement bancaire"]})
    facture: Optional[str] = Field(default=None, json_schema_extra={"examples": ["FAC-2024-001"]})
    motifGeneral: Optional[str] = Field(default=None, json_schema_extra={"examples": ["Produit défectueux"]})

class Product(BaseModel):
    designation: str = Field(default=..., json_schema_extra={"examples": ["Produit A"]})
    quantite: float = Field(default=..., json_schema_extra={"examples": [10]})
    unite: str = Field(default=..., json_schema_extra={"examples": ["pièce"]})
    prixUnitaire: Optional[float] = Field(default=None, json_schema_extra={"examples": [100.5]})
    tauxTVA: Optional[float] = Field(default=None, json_schema_extra={"examples": [19]})
    observation: Optional[str] = Field(default=None, json_schema_extra={"examples": ["Aucune observation"]})
    motifRetour: Optional[str] = Field(default=None, json_schema_extra={"examples": ["Produit défectueux"]})

class Totals(BaseModel):
    totalHT: str = Field(default=...)
    totalTVA: str = Field(default=...)
    totalTTC: str = Field(default=...)

class GeneratePdfRequest(BaseModel):
    type: Literal[
        "bon-livraison",
        "bon-commande",
        "facture",
        "facture-proforma",
        "proforma",
        "bon-retour",
        "facture-avoir",
        "bon-versement",
        "bon-reception"
    ] = Field(default=..., json_schema_extra={"examples": ["facture"]})
    companyInfo: CompanyInfo
    clientInfo: ClientInfo
    documentInfo: DocumentInfo
    products: List[Product]
    totals: Optional[Totals] = None
    logoUrl: Optional[str] = Field(default=None, json_schema_extra={"examples": ["https://example.com/logo.png"]})

# Setup Jinja2 environment
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(templates_dir, exist_ok=True)

env = Environment(
    loader=FileSystemLoader(templates_dir),
    autoescape=select_autoescape(['html', 'xml'])
)

# Add custom filters
def format_currency(value):
    """Format number as currency"""
    if value is None:
        return "0.00"
    return f"{float(value):,.2f}"

def format_date(date_str):
    """Format date string"""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%d/%m/%Y")
    except:
        return date_str

env.filters['currency'] = format_currency
env.filters['date'] = format_date

def get_document_title(doc_type: str) -> str:
    """Get document title based on type"""
    titles = {  
        "bon-livraison": "BON DE LIVRAISON",
        "bon-commande": "BON DE COMMANDE",
        "facture": "FACTURE",
        "facture-proforma": "FACTURE PROFORMA",
        "proforma": "FACTURE PROFORMA",
        "bon-retour": "BON DE RETOUR",
        "facture-avoir": "FACTURE AVOIR",
        "bon-versement": "BON DE VERSEMENT",
        "bon-reception": "BON DE RÉCEPTION"
    }
    return titles.get(doc_type, "DOCUMENT")


# --- Number to words utility (French, Dinar) ---
def number_to_french_words(n):
    # Handles integer and decimal part for dinars/centimes
    try:
        entier = int(n)
        centimes = int(round((n - entier) * 100))
        words = num2words(entier, lang='fr') + " dinar"
        if entier > 1 or entier == 0:
            words += "s"
        if centimes > 0:
            words += f" et {num2words(centimes, lang='fr')} centime"
            if centimes > 1:
                words += "s"
        return words
    except Exception:
        return str(n)

def calculate_line_total(product: Product) -> float:
    """Calculate total for a product line"""
    if product.prixUnitaire is None:
        return 0.0
    subtotal = product.quantite * product.prixUnitaire
    if product.tauxTVA:
        return subtotal * (1 + product.tauxTVA / 100)
    return subtotal

@app.post("/generate-pdf")
async def generate_pdf(request: GeneratePdfRequest):
    try:
        # Get the appropriate template
        template_name = f"{request.type}.html"
        
        try:
            template = env.get_template(template_name)
        except:
            # Use a generic template if specific one doesn't exist
            template = env.get_template("bon-livraison.html")
        
        # Calculate totals if not provided
        totals = request.totals
        if not totals and request.products:
            total_ht = sum(
                (p.quantite * (p.prixUnitaire or 0)) for p in request.products
            )
            total_tva = sum(
                (p.quantite * (p.prixUnitaire or 0) * (p.tauxTVA or 0) / 100) 
                for p in request.products
            )
            total_ttc = total_ht + total_tva
            
            totals = Totals(
                totalHT=f"{total_ht:.2f}",
                totalTVA=f"{total_tva:.2f}",
                totalTTC=f"{total_ttc:.2f}"
            )
        
        # Prepare total_ttc_words for templates

        if totals is not None:
            try:
                total_ttc_value = float(totals.totalTTC)
            except Exception:
                total_ttc_value = 0
            total_ttc_words = number_to_french_words(total_ttc_value)
        else:
            total_ttc_words = "zéro"

        # Prepare template context
        context = {
            "document_title": get_document_title(request.type),
            "company": request.companyInfo,
            "client": request.clientInfo,
            "document": request.documentInfo,
            "products": request.products,
            "totals": totals,
            "type": request.type,
            "generated_date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "total_ttc_words": total_ttc_words,
            "logo_url": request.logoUrl
        }
        
        # Render HTML
        html_content = template.render(**context)

        # CSS for A4 page size
        a4_css = CSS(string='@page { size: A4; margin: 20mm 15mm 20mm 15mm; }')

        # Generate PDF using WeasyPrint with A4 size
        html_doc = HTML(string=html_content)
        pdf_bytes = html_doc.write_pdf(stylesheets=[a4_css])

        # Return PDF as response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={request.documentInfo.numero}.pdf"
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "pdf-generation"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)