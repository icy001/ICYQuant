"""
Report exporter.
"""

import json


class ReportExporter:

    def export_json(
        self,
        report,
    ):

        return json.dumps(
            report.__dict__,
            default=str,
            indent=2,
        )


    def export_html(
        self,
        report,
    ):

        return f"""
        <html>
        <body>
        <h1>Backtest Report</h1>
        <pre>{report}</pre>
        </body>
        </html>
        """