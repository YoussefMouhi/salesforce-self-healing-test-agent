public with sharing class ProductCatalogController {

    @AuraEnabled(cacheable=true)
    public static List<PricebookEntry> getProducts(String testAccountId) {
        String assignedPriceBook = resolveAssignedPriceBook(testAccountId);

        return [
            SELECT Id, Product2.Name, Product2.Description,
                   UnitPrice, Pricebook2.Name
            FROM PricebookEntry
            WHERE IsActive = true
            AND Pricebook2.Name = :assignedPriceBook
            ORDER BY Product2.Name
            LIMIT 50
        ];
    }

    private static String resolveAssignedPriceBook(String testAccountId) {
        String result = 'Standard Price Book';
        Id accountIdToUse;

        if (String.isNotBlank(testAccountId)) {
            accountIdToUse = Id.valueOf(testAccountId);
        } else {
            User currentUser = [
                SELECT AccountId
                FROM User
                WHERE Id = :UserInfo.getUserId()
                LIMIT 1
            ];
            accountIdToUse = currentUser.AccountId;
        }

        if (accountIdToUse != null) {
            List<Account> accs = [
                SELECT Assigned_Price_Book__c
                FROM Account
                WHERE Id = :accountIdToUse
                LIMIT 1
            ];
            if (!accs.isEmpty() && String.isNotBlank(accs[0].Assigned_Price_Book__c)) {
                result = accs[0].Assigned_Price_Book__c;
            }
        }

        return result;
    }
}
