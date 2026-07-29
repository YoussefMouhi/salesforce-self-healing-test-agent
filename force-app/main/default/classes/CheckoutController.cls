public with sharing class CheckoutController {

    public class CartLineInput {
        @AuraEnabled public Id productId;
        @AuraEnabled public Integer quantity;
    }

    public class CheckoutResult {
        @AuraEnabled public Id orderId;
        @AuraEnabled public Decimal totalAmount;
        @AuraEnabled public Boolean approvalRequired;
    }

    private static final Decimal APPROVAL_THRESHOLD = 10000;

    @AuraEnabled
    public static CheckoutResult submitOrder(String testAccountId, String linesJson) {
        List<CartLineInput> lines = (List<CartLineInput>) JSON.deserialize(linesJson, List<CartLineInput>.class);

        if (lines == null || lines.isEmpty()) {
            throw new AuraHandledException('Cart is empty.');
        }

        Id accountId = resolveAccountId(testAccountId);
        Id pricebookId = resolveAssignedPricebookId(accountId);

        Set<Id> productIds = new Set<Id>();
        for (CartLineInput line : lines) {
            productIds.add(line.productId);
        }

        Map<Id, PricebookEntry> entriesByProduct = new Map<Id, PricebookEntry>();
        for (PricebookEntry pbe : [
            SELECT Id, Product2Id, UnitPrice
            FROM PricebookEntry
            WHERE Pricebook2Id = :pricebookId
            AND Product2Id IN :productIds
            AND IsActive = true
        ]) {
            entriesByProduct.put(pbe.Product2Id, pbe);
        }

        Decimal total = 0;
        for (CartLineInput line : lines) {
            PricebookEntry pbe = entriesByProduct.get(line.productId);
            if (pbe == null) {
                throw new AuraHandledException('No active price found for product ' + line.productId + ' in the resolved price book.');
            }
            total += pbe.UnitPrice * line.quantity;
        }

        Boolean needsApproval = total > APPROVAL_THRESHOLD;

        Order ord = new Order(
            AccountId = accountId,
            Pricebook2Id = pricebookId,
            EffectiveDate = Date.today(),
            Status = 'Draft',
            Approval_Required__c = needsApproval
        );
        insert ord;

        List<OrderItem> orderItems = new List<OrderItem>();
        for (CartLineInput line : lines) {
            PricebookEntry pbe = entriesByProduct.get(line.productId);
            orderItems.add(new OrderItem(
                OrderId = ord.Id,
                PricebookEntryId = pbe.Id,
                Quantity = line.quantity,
                UnitPrice = pbe.UnitPrice
            ));
        }
        insert orderItems;

        CheckoutResult result = new CheckoutResult();
        result.orderId = ord.Id;
        result.totalAmount = total;
        result.approvalRequired = needsApproval;
        return result;
    }

    private static Id resolveAccountId(String testAccountId) {
        if (String.isNotBlank(testAccountId)) {
            return (Id) testAccountId;
        }
        return null;
    }

    private static Id resolveAssignedPricebookId(Id accountId) {
        String targetName = 'Standard Price Book';

        if (accountId != null) {
            Account acc = [SELECT Assigned_Price_Book__c FROM Account WHERE Id = :accountId LIMIT 1];
            if (String.isNotBlank(acc.Assigned_Price_Book__c)) {
                targetName = acc.Assigned_Price_Book__c;
            }
        }

        List<Pricebook2> books = [SELECT Id FROM Pricebook2 WHERE Name = :targetName LIMIT 1];
        if (books.isEmpty()) {
            throw new AuraHandledException('Price book not found: ' + targetName);
        }
        return books[0].Id;
    }
}
