"""OFX (Open Financial Exchange) import support."""

from datetime import datetime
from decimal import Decimal
from typing import List

try:
    from ofxparse import OfxParser
    OFX_AVAILABLE = True
except ImportError:
    OFX_AVAILABLE = False

from .models import Transaction, TransactionStatus


class OFXImporter:
    """Import transactions from OFX files."""
    
    @staticmethod
    def is_available() -> bool:
        """Check if OFX parsing is available."""
        return OFX_AVAILABLE
    
    @staticmethod
    def parse_file(file_path: str) -> List[Transaction]:
        """Parse OFX file and return list of transactions."""
        if not OFX_AVAILABLE:
            raise ImportError("ofxparse library not available. Install with: pip install ofxparse")
        
        with open(file_path, 'rb') as f:
            ofx = OfxParser.parse(f)
        
        transactions = []
        
        # OFX can contain multiple accounts
        for account in ofx.accounts:
            for ofx_trans in account.statement.transactions:
                transaction = Transaction()
                transaction.date = ofx_trans.date.date() if hasattr(ofx_trans.date, 'date') else ofx_trans.date
                transaction.amount = Decimal(str(ofx_trans.amount))
                transaction.payee = ofx_trans.payee or ""
                transaction.memo = ofx_trans.memo or ""
                
                # OFX transaction ID could be used as check number
                if hasattr(ofx_trans, 'checknum') and ofx_trans.checknum:
                    transaction.check_number = ofx_trans.checknum
                
                transactions.append(transaction)
        
        return transactions
