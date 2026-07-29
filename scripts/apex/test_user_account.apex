User me = [SELECT Id, AccountId FROM User WHERE Id = :UserInfo.getUserId()];
System.debug('My AccountId: ' + me.AccountId);

if (me.AccountId != null) {
    Account acc = [SELECT Name, Assigned_Price_Book__c FROM Account WHERE Id = :me.AccountId];
    System.debug('My Account Name: ' + acc.Name);
    System.debug('My Assigned Price Book: ' + acc.Assigned_Price_Book__c);
}
