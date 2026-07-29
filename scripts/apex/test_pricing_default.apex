List<PricebookEntry> result = ProductCatalogController.getProducts(null);
System.debug('Result count: ' + result.size());
for (PricebookEntry pbe : result) {
    System.debug(pbe.Product2.Name + ' -> ' + pbe.UnitPrice + ' (' + pbe.Pricebook2.Name + ')');
}
