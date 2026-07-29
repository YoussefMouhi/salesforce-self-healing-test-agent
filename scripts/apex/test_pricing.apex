System.debug('--- Standard test ---');
List<Account> stdAcc = [SELECT Id FROM Account WHERE Name = 'Acme Standard Buyer' LIMIT 1];
List<PricebookEntry> stdResult = ProductCatalogController.getProducts(String.valueOf(stdAcc[0].Id));
for (PricebookEntry pbe : stdResult) {
    System.debug(pbe.Product2.Name + ' -> ' + pbe.UnitPrice + ' (' + pbe.Pricebook2.Name + ')');
}

System.debug('--- Negotiated test ---');
List<Account> negAcc = [SELECT Id FROM Account WHERE Name = 'Acme Negotiated Buyer' LIMIT 1];
List<PricebookEntry> negResult = ProductCatalogController.getProducts(String.valueOf(negAcc[0].Id));
for (PricebookEntry pbe : negResult) {
    System.debug(pbe.Product2.Name + ' -> ' + pbe.UnitPrice + ' (' + pbe.Pricebook2.Name + ')');
}
